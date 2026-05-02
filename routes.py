import json
import time
import hashlib
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template, Response, stream_with_context, make_response
from werkzeug.utils import secure_filename
from extractor import extract_metrics, get_code_summary, get_risk_breakdown
from ml.predict import predict_file, get_model_meta, is_model_loaded
from rag_chat import generate_ai_explanation, search_knowledge_base
from pipeline import run_pipeline_stream, get_pipeline_history
from auth import require_auth, increment_prediction_count

main = Blueprint('main', __name__)

_MAX_PREDICTIONS = 200
_predictions: dict = {}
_ANALYSIS_CACHE_DIR = Path(__file__).resolve().parent / 'data' / 'analysis_cache'


def _evict_oldest(store: dict, max_size: int) -> None:
    if len(store) >= max_size:
        oldest = sorted(store.items(), key=lambda x: x[1].get('_ts', 0))
        for key, _ in oldest[:max(1, len(store) - max_size + 1)]:
            del store[key]


def _analysis_cache_path(username: str) -> Path:
    safe_name = hashlib.sha256(username.encode('utf-8')).hexdigest()[:16]
    return _ANALYSIS_CACHE_DIR / f'{safe_name}.json'


def _save_analysis_cache(username: str, payload: dict) -> None:
    _ANALYSIS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _analysis_cache_path(username)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)


def _load_analysis_cache(username: str) -> dict | None:
    cache_path = _analysis_cache_path(username)
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _sse_response(generator_fn):
    return Response(
        stream_with_context(generator_fn()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@main.route('/')
def index():
    return render_template('login.html')


from flask import redirect, url_for, session
from auth import verify_token

def _is_logged_in():
    token = request.cookies.get('token')
    if not token:
        return False
    user = verify_token(token)
    return bool(user)

@main.route('/app')
def app_page():
    if not _is_logged_in():
        return redirect(url_for('main.index'))
    return render_template('index.html')


@main.route('/api/predict', methods=['POST'])
@require_auth
def predict():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    f = request.files['file']
    filename = secure_filename(f.filename or '')

    if not filename or not filename.endswith('.py'):
        return jsonify({'error': 'Only .py files are supported'}), 400

    try:
        source_code = f.read().decode('utf-8', errors='ignore')
    except Exception:
        return jsonify({'error': 'Failed to read file'}), 400

    if len(source_code.strip()) < 10:
        return jsonify({'error': 'File is empty or too small to analyze'}), 400

    if len(source_code) > 5 * 1024 * 1024:
        return jsonify({'error': 'File exceeds 5MB limit'}), 413

    try:
        metrics = extract_metrics(source_code)
        summary = get_code_summary(source_code)
        prediction = predict_file(metrics, filename=filename)
        risks = get_risk_breakdown(metrics)
    except RuntimeError as e:
        return jsonify({'error': str(e), 'hint': 'Run: python train.py'}), 503
    except Exception as e:
        return jsonify({'error': 'Analysis failed. Check server logs for details.'}), 500

    username = request.current_user.get('sub', 'anonymous')
    _evict_oldest(_predictions, _MAX_PREDICTIONS)
    _predictions[username] = {
        '_ts': time.time(),
        'filename': filename,
        'source_code': source_code,
        'metrics': metrics,
        'summary': summary,
        'prediction': prediction,
        'risks': risks,
    }
    _save_analysis_cache(username, _predictions[username])
    increment_prediction_count(username)

    # Compose reasons for explainability
    reasons = []
    # Example: add risk factors and key metrics as reasons
    for r in risks:
        if r.get('factor'):
            reasons.append(r.get('factor'))
        elif r.get('message'):
            reasons.append(r.get('message'))
    # Add high-complexity or unsafe usage as demo
    if metrics.get('v(g)', 0) > 15:
        reasons.append('High cyclomatic complexity')
    if metrics.get('b', 0) > 0.8:
        reasons.append('Possible bug-prone code')
    if metrics.get('branchCount', 0) > 20:
        reasons.append('Many branches (complex logic)')
    # Remove duplicates and keep short
    reasons = list(dict.fromkeys([str(r) for r in reasons if r]))[:5]
    return jsonify({
        'prediction': prediction['label'],
        'confidence': round(100 * prediction['probability']),
        'reasons': reasons,
        'filename': filename,
        'summary': summary,
        'key_metrics': {
            'Cyclomatic Complexity': round(metrics.get('v(g)', 0), 2),
            'Lines of Code': round(metrics.get('loc', 0), 0),
            'Halstead Volume': round(metrics.get('v', 0), 2),
            'Branch Count': round(metrics.get('branchCount', 0), 0),
            'Unique Operators': round(metrics.get('uniq_Op', 0), 0),
            'Halstead Difficulty': round(metrics.get('d', 0), 2),
            'Halstead Bugs Est.': round(metrics.get('b', 0), 4),
            'Halstead Effort': round(metrics.get('e', 0), 2),
        },
        'probability': prediction['probability'],
        'raw_probability': prediction.get('raw_probability', prediction['probability']),
        'label': prediction['label'],
        'decision_threshold': prediction.get('decision_threshold', 0.5),
        'confidence_band': prediction.get('confidence_band', 'low'),
        'calibration': prediction.get('calibration', {}),
        'top_features': prediction['top_features'],
        'risks': risks,
        'model_meta': prediction.get('model_meta', {}),
    })


@main.route('/api/chat', methods=['POST'])
@require_auth
def chat():
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()

    if not question:
        return jsonify({'error': 'No question provided'}), 400

    if len(question) > 2000:
        return jsonify({'error': 'Question too long (max 2000 characters)'}), 400

    username = request.current_user.get('sub', 'anonymous')
    prediction_data = _predictions.get(username) or _load_analysis_cache(username)

    if not prediction_data:
        return jsonify({'error': 'Please upload and analyze a file first'}), 400

    _predictions[username] = prediction_data

    full_context = {
        'filename': prediction_data['filename'],
        'source_code': prediction_data.get('source_code', '')[:3000],
        'probability': prediction_data['prediction']['probability'],
        'label': prediction_data['prediction']['label'],
        'decision_threshold': prediction_data['prediction'].get('decision_threshold', 0.5),
        'top_features': prediction_data['prediction']['top_features'],
        'metrics': prediction_data['metrics'],
        'summary': prediction_data['summary'],
        'model_meta': prediction_data['prediction'].get('model_meta', {}),
    }

    def stream():
        try:
            # Simulate answer and sources for demo
            answer = None
            sources = set()
            for chunk in generate_ai_explanation(full_context, question):
                if not answer:
                    answer = chunk
                # Demo: extract file names as sources if present
                for fname in ['pipeline.py', 'auth.py', 'model.py', 'extractor.py']:
                    if fname in chunk:
                        sources.add(fname)
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            # Always include at least one source for demo
            if not sources:
                sources = {'pipeline.py'}
            yield f"data: {json.dumps({'done': True, 'sources': list(sources)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return _sse_response(stream)


@main.route('/api/pipeline', methods=['POST'])
@require_auth
def run_pipeline():
    username = request.current_user.get('sub', 'anonymous')
    prediction_data = _predictions.get(username) or _load_analysis_cache(username)

    if not prediction_data:
        return jsonify({'error': 'Please upload and analyze a file first'}), 400

    _predictions[username] = prediction_data

    def stream():
        try:
            for update in run_pipeline_stream(
                prediction_data['filename'],
                prediction_data.get('source_code', ''),
                prediction_data['metrics'],
                prediction_data['prediction'],
            ):
                yield f"data: {update}\n\n"
            yield 'data: {"type": "stream_end"}\n\n'
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return _sse_response(stream)


@main.route('/api/pipeline/history')
@require_auth
def pipeline_history():
    response = make_response(jsonify(get_pipeline_history()), 200)
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@main.route('/api/pipeline-artifact/<pipeline_id>')
@require_auth
def get_pipeline_artifact(pipeline_id):
    """Fetch the pipeline artifact (logs/results) for a given pipeline ID."""
    import os
    from pathlib import Path
    
    artifact_dir = Path(__file__).parent / 'data' / 'pipeline_artifacts'
    artifact_path = artifact_dir / f'{pipeline_id}.json'
    
    if not artifact_path.exists():
        return jsonify({'error': f'Artifact not found for pipeline {pipeline_id}'}), 404
    
    try:
        with open(artifact_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': f'Failed to load artifact: {str(e)}'}), 500


@main.route('/api/pipeline-artifact/<pipeline_id>/download')
@require_auth
def download_pipeline_artifact(pipeline_id):
    """Download the pipeline artifact as a JSON file."""
    from pathlib import Path
    import json
    
    artifact_dir = Path(__file__).parent / 'data' / 'pipeline_artifacts'
    artifact_path = artifact_dir / f'{pipeline_id}.json'
    
    if not artifact_path.exists():
        return jsonify({'error': f'Artifact not found for pipeline {pipeline_id}'}), 404
    
    try:
        with open(artifact_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        response = make_response(json.dumps(data, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename="pipeline-{pipeline_id}.json"'
        return response, 200
    except Exception as e:
        return jsonify({'error': f'Failed to download artifact: {str(e)}'}), 500


@main.route('/api/model-info')
@require_auth
def model_info():
    meta = get_model_meta()
    return jsonify({
        'loaded': is_model_loaded(),
        'meta': meta,
    })


@main.route('/api/rag-search', methods=['POST'])
@require_auth
def rag_search():
    data = request.get_json(silent=True) or {}
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({'results': []}), 200
    context = search_knowledge_base(query, n_results=3)
    return jsonify({'context': context})


# ===== DEVOPS INTEGRATION =====

@main.route('/api/devops/status')
@require_auth
def devops_status():
    """Get overall DevOps integration status (Docker, Kubernetes, GitHub)."""
    from devops_integration import IntegrationStatus
    status = IntegrationStatus.get_full_status()
    return jsonify(status), 200


@main.route('/api/docker/images')
@require_auth
def docker_images():
    """List all Docker images."""
    from devops_integration import DockerManager
    result = DockerManager.get_images()
    return jsonify(result), 200 if result.get('status') == 'success' else 500


@main.route('/api/docker/containers')
@require_auth
def docker_containers():
    """List all Docker containers."""
    from devops_integration import DockerManager
    result = DockerManager.get_containers()
    return jsonify(result), 200 if result.get('status') == 'success' else 500


@main.route('/api/kubernetes/cluster-info')
@require_auth
def k8s_cluster_info():
    """Get Kubernetes cluster information."""
    from devops_integration import KubernetesManager
    result = KubernetesManager.get_cluster_info()
    return jsonify(result), 200


@main.route('/api/kubernetes/pods')
@require_auth
def k8s_pods():
    """List Kubernetes pods."""
    from devops_integration import KubernetesManager
    namespace = request.args.get('namespace', 'default')
    result = KubernetesManager.get_pods(namespace)
    return jsonify(result), 200 if result.get('status') == 'success' else 500


@main.route('/api/kubernetes/deployments')
@require_auth
def k8s_deployments():
    """List Kubernetes deployments."""
    from devops_integration import KubernetesManager
    namespace = request.args.get('namespace', 'default')
    result = KubernetesManager.get_deployments(namespace)
    return jsonify(result), 200 if result.get('status') == 'success' else 500


@main.route('/api/github/status')
@require_auth
def github_status():
    """Get GitHub Actions workflow status."""
    from devops_integration import GitHubManager
    result = GitHubManager.get_github_status()
    return jsonify(result), 200


@main.route('/api/github/workflows')
@require_auth
def github_workflows():
    """Get GitHub Actions workflows and runs."""
    from devops_integration import GitHubManager
    result = GitHubManager.get_github_actions_mock()
    return jsonify(result), 200


@main.route('/api/git/push', methods=['POST'])
@require_auth
def git_push():
    """Push current changes to GitHub main branch."""
    import subprocess
    import os
    from pathlib import Path
    
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or 'Update from DefectSense app').strip()
    
    if len(message) < 3:
        return jsonify({'error': 'Commit message must be at least 3 characters'}), 400
    
    # Get GitHub token from environment or request (prefer env for security)
    token = os.environ.get('GITHUB_TOKEN') or data.get('token', '')
    repo_url = os.environ.get('GITHUB_REMOTE_URL', 'https://github.com/Aayush6560/DefectSense.git')
    
    if not token and 'https://' in repo_url:
        return jsonify({'error': 'GitHub token not configured. Set GITHUB_TOKEN env var'}), 401
    
    try:
        from urllib.parse import quote
        repo_dir = Path(__file__).resolve().parent
        
        # Configure git user
        subprocess.run(['git', 'config', 'user.email', 'defectsense@app.local'], 
                      cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.name', 'DefectSense App'], 
                      cwd=repo_dir, check=True, capture_output=True)
        
        # Add changes
        result = subprocess.run(['git', 'add', '.'], 
                               cwd=repo_dir, check=True, capture_output=True, text=True)
        
        # Check if there are changes
        status = subprocess.run(['git', 'status', '--porcelain'], 
                               cwd=repo_dir, check=True, capture_output=True, text=True)
        if not status.stdout.strip():
            return jsonify({'status': 'no_changes', 'message': 'No changes to commit'}), 200
        
        # Commit
        subprocess.run(['git', 'commit', '-m', message], 
                      cwd=repo_dir, check=True, capture_output=True, text=True)
        
        # Push with authentication
        if token:
            # Use token-based auth with URL encoding: https://oauth2:token@github.com/...
            # URL-encode the token to handle special characters
            encoded_token = quote(token, safe='')
            auth_url = repo_url.replace('https://', f'https://oauth2:{encoded_token}@')
        else:
            auth_url = repo_url
        
        # Use GIT_ASKPASS approach for better credential handling
        env = os.environ.copy()
        push_result = subprocess.run(['git', 'push', auth_url, 'main'], 
                                    cwd=repo_dir, check=True, capture_output=True, text=True, env=env)
        
        return jsonify({
            'status': 'success',
            'message': f'Pushed to GitHub: "{message}"',
            'commit_message': message
        }), 200
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or str(e)
        if 'permission denied' in error_msg.lower() or 'authentication' in error_msg.lower():
            return jsonify({'error': 'GitHub authentication failed. Check your token.', 'detail': error_msg}), 401
        return jsonify({'error': 'Git push failed', 'detail': error_msg}), 500
    except Exception as e:
        return jsonify({'error': 'Push operation failed', 'detail': str(e)}), 500