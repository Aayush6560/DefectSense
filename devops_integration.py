"""
DevOps Integration Module
Connects Docker, Kubernetes, GitHub Actions, and CI/CD Pipeline
"""

import json
import subprocess
import os
import itertools
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timedelta, timezone
import shutil
import tempfile

try:
    import docker as docker_sdk
except ImportError:
    docker_sdk = None

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))


class DockerManager:
    """Manage Docker containers and images."""

    _PROJECT_IMAGE_NAME = 'proj3-defectsense'

    @staticmethod
    def _get_client():
        if docker_sdk is None:
            return None, {'status': 'error', 'message': 'Python docker SDK not installed'}
        try:
            return docker_sdk.from_env(timeout=10), None
        except Exception as exc:
            return None, {'status': 'error', 'message': str(exc)}

    @staticmethod
    def _format_size(size_value):
        if size_value is None:
            return 'N/A'
        try:
            size_bytes = float(size_value)
        except (TypeError, ValueError):
            return str(size_value)

        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        while size_bytes >= 1024 and unit_index < len(units) - 1:
            size_bytes /= 1024
            unit_index += 1
        return f'{size_bytes:.1f} {units[unit_index]}'

    @staticmethod
    def _is_project_image(image_name):
        if not image_name:
            return False
        normalized = image_name.lower()
        return normalized == DockerManager._PROJECT_IMAGE_NAME or normalized.startswith(f'{DockerManager._PROJECT_IMAGE_NAME}:')

    @staticmethod
    def _image_sort_key(image_record):
        created = image_record.get('created')
        if not created or created == 'N/A':
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(str(created).replace('Z', '+00:00'))
        except Exception:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    @staticmethod
    def get_images():
        """List all Docker images."""
        client, error = DockerManager._get_client()
        if error:
            return error
        try:
            images = []
            for image in client.images.list():
                try:
                    tags = image.tags or ['<none>:<none>']
                    primary_tag = tags[0]
                    if ':' in primary_tag:
                        repository, tag = primary_tag.rsplit(':', 1)
                    else:
                        repository, tag = primary_tag, 'latest'
                    if not DockerManager._is_project_image(repository):
                        continue
                    images.append({
                        'repository': repository,
                        'tag': tag,
                        'image_id': image.id.replace('sha256:', '')[:12],
                        'size': DockerManager._format_size(image.attrs.get('Size')),
                        'created': image.attrs.get('Created', 'N/A'),
                    })
                except Exception:
                    # Some dangling images or metadata snapshots can disappear between list and inspect.
                    continue
            images.sort(key=DockerManager._image_sort_key, reverse=True)
            images = images[:5]
            return {'status': 'success', 'images': images}
        except Exception as exc:
            return {'status': 'error', 'message': str(exc)}
        finally:
            try:
                client.close()
            except Exception:
                pass
    
    @staticmethod
    def get_containers():
        """List all Docker containers."""
        client, error = DockerManager._get_client()
        if error:
            return error
        try:
            containers = []
            for container in client.containers.list(all=True):
                container_attrs = container.attrs or {}
                config = container_attrs.get('Config', {})
                image_name = config.get('Image') or '<unknown image>'
                image_id = container_attrs.get('Image', '')
                try:
                    image_obj = getattr(container, 'image', None)
                    tags = getattr(image_obj, 'tags', None) or [image_name]
                except Exception:
                    tags = [image_name]
                if not container.name.startswith(DockerManager._PROJECT_IMAGE_NAME):
                    continue
                if not DockerManager._is_project_image(tags[0]):
                    continue
                ports = container.attrs.get('NetworkSettings', {}).get('Ports', {})
                containers.append({
                    'id': container.id[:12],
                    'image': tags[0],
                    'image_id': image_id.replace('sha256:', '')[:12] if image_id else '',
                    'name': container.name,
                    'status': container.status,
                    'created': container_attrs.get('Created', 'N/A'),
                    'ports': json.dumps(ports),
                })
            return {'status': 'success', 'containers': containers}
        except Exception as exc:
            return {'status': 'error', 'message': str(exc)}
        finally:
            try:
                client.close()
            except Exception:
                pass


class KubernetesManager:
    """Manage Kubernetes clusters and deployments."""

    @staticmethod
    def _kubectl_env():
        """Return an env mapping that points kubectl at a reachable kubeconfig."""
        kubeconfig = os.environ.get('KUBECONFIG')
        if not kubeconfig:
            return None

        try:
            kube_path = Path(kubeconfig)
            if not kube_path.exists():
                return None

            original_lines = kube_path.read_text(encoding='utf-8', errors='ignore').splitlines()
            rewritten_lines = []
            changed = False
            for index, line in enumerate(original_lines):
                if line.strip().startswith('certificate-authority-data:') or line.strip().startswith('certificate-authority:'):
                    changed = True
                    continue
                updated_line = line.replace('https://127.0.0.1:', 'https://host.docker.internal:')
                updated_line = updated_line.replace('https://localhost:', 'https://host.docker.internal:')
                rewritten_lines.append(updated_line)
                if updated_line.strip().startswith('server: https://host.docker.internal:'):
                    next_line = original_lines[index + 1].strip() if index + 1 < len(original_lines) else ''
                    if not next_line.startswith('insecure-skip-tls-verify:'):
                        indent = updated_line[:len(updated_line) - len(updated_line.lstrip())]
                        rewritten_lines.append(f'{indent}insecure-skip-tls-verify: true')
                        changed = True
                if updated_line != line:
                    changed = True

            if not changed:
                return None

            rewritten = '\n'.join(rewritten_lines) + ('\n' if original_lines else '')

            temp_file = tempfile.NamedTemporaryFile('w', delete=False, suffix='.kubeconfig')
            temp_file.write(rewritten)
            temp_file.flush()
            temp_file.close()

            env = os.environ.copy()
            env['KUBECONFIG'] = temp_file.name
            return env
        except Exception:
            return None
    
    @staticmethod
    def get_cluster_info():
        """Get Kubernetes cluster info."""
        try:
            kubectl_env = KubernetesManager._kubectl_env()
            result = subprocess.run(
                ['kubectl', 'cluster-info'],
                capture_output=True,
                text=True,
                timeout=10
                ,env=kubectl_env
            )
            if result.returncode == 0:
                return {
                    'status': 'connected',
                    'info': result.stdout.strip()
                }
            return {
                'status': 'disconnected',
                'info': result.stderr or 'Cluster not reachable'
            }
        except FileNotFoundError:
            return {
                'status': 'not_installed',
                'info': 'kubectl not found in the container. Mount host kubeconfig and install kubectl to read Docker Desktop Kubernetes.'
            }
        except Exception as e:
            return {'status': 'error', 'info': str(e)}
    
    @staticmethod
    def get_pods(namespace='default'):
        """List Kubernetes pods in a namespace."""
        try:
            kubectl_env = KubernetesManager._kubectl_env()
            result = subprocess.run(
                ['kubectl', 'get', 'pods', '-n', namespace, '-o', 'json'],
                capture_output=True,
                text=True,
                timeout=10,
                env=kubectl_env
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                pods = []
                for item in data.get('items', []):
                    metadata = item.get('metadata', {})
                    status = item.get('status', {})
                    pods.append({
                        'name': metadata.get('name', 'N/A'),
                        'namespace': metadata.get('namespace', 'N/A'),
                        'status': status.get('phase', 'Unknown'),
                        'ready': f"{sum(1 for c in status.get('conditions', []) if c.get('status') == 'True')}/{len(status.get('conditions', []))}",
                        'restarts': sum(c.get('restartCount', 0) for c in status.get('containerStatuses', [])),
                        'age': metadata.get('creationTimestamp', 'N/A'),
                    })
                return {'status': 'success', 'pods': pods, 'namespace': namespace}
            return {'status': 'error', 'message': result.stderr or 'Failed to list pods'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def get_deployments(namespace='default'):
        """List Kubernetes deployments."""
        try:
            kubectl_env = KubernetesManager._kubectl_env()
            result = subprocess.run(
                ['kubectl', 'get', 'deployments', '-n', namespace, '-o', 'json'],
                capture_output=True,
                text=True,
                timeout=10,
                env=kubectl_env
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                deployments = []
                for item in data.get('items', []):
                    metadata = item.get('metadata', {})
                    spec = item.get('spec', {})
                    status = item.get('status', {})
                    deployments.append({
                        'name': metadata.get('name', 'N/A'),
                        'namespace': metadata.get('namespace', 'N/A'),
                        'replicas_desired': spec.get('replicas', 0),
                        'replicas_ready': status.get('readyReplicas', 0),
                        'replicas_updated': status.get('updatedReplicas', 0),
                        'image': spec.get('template', {}).get('spec', {}).get('containers', [{}])[0].get('image', 'N/A'),
                        'age': metadata.get('creationTimestamp', 'N/A'),
                    })
                return {'status': 'success', 'deployments': deployments, 'namespace': namespace}
            return {'status': 'error', 'message': result.stderr or 'Failed to list deployments'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


class GitHubManager:
    """Manage GitHub Actions and CI/CD pipelines."""

    @staticmethod
    def _parse_github_remote():
        """Extract owner/repo from the local GitHub remote URL."""
        try:
            env_repo = os.environ.get('GITHUB_REPOSITORY', '').strip()
            if env_repo and '/' in env_repo:
                owner, repo = env_repo.split('/', 1)
                return {
                    'owner': owner.strip(),
                    'repo': repo.strip().removesuffix('.git'),
                    'remote_url': os.environ.get('GITHUB_REMOTE_URL', '').strip() or f'https://github.com/{env_repo}',
                }

            env_remote = os.environ.get('GITHUB_REMOTE_URL', '').strip()
            if env_remote:
                match = re.search(r'github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$', env_remote)
                if match:
                    return {
                        'owner': match.group('owner'),
                        'repo': match.group('repo'),
                        'remote_url': env_remote,
                    }

            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(ROOT),
            )
            if result.returncode != 0:
                return None

            remote_url = (result.stdout or '').strip()
            if not remote_url:
                return None

            match = re.search(r'github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$', remote_url)
            if not match:
                return None

            return {
                'owner': match.group('owner'),
                'repo': match.group('repo'),
                'remote_url': remote_url,
            }
        except Exception:
            return None

    @staticmethod
    def _github_api_get(path, params=None):
        """Make an unauthenticated GitHub API request for public repositories."""
        query = urllib.parse.urlencode(params or {})
        url = f'https://api.github.com{path}'
        if query:
            url = f'{url}?{query}'

        request = urllib.request.Request(
            url,
            headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'DefectSense-DevOps-Dashboard',
            },
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))

    @staticmethod
    def _format_commit(commit):
        commit_data = commit.get('commit', {})
        author = commit_data.get('author', {})
        sha = (commit.get('sha') or '')[:7]
        message = (commit_data.get('message') or '').split('\n', 1)[0]
        return {
            'id': sha,
            'message': message,
            'author': author.get('name') or commit.get('author', {}).get('login') or 'unknown',
            'timestamp': author.get('date') or commit_data.get('committer', {}).get('date'),
            'source': 'github-api',
        }

    @staticmethod
    def _get_public_github_activity(limit=10):
        """Return public GitHub commits for today if the repository is accessible."""
        remote = GitHubManager._parse_github_remote()
        if not remote:
            return []

        since = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        try:
            commits = GitHubManager._github_api_get(
                f"/repos/{remote['owner']}/{remote['repo']}/commits",
                {'since': since, 'per_page': limit},
            )
            if not isinstance(commits, list):
                return []
            return [GitHubManager._format_commit(commit) for commit in commits[:limit]]
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, json.JSONDecodeError):
            return []

    @staticmethod
    def _get_recent_git_activity(limit=10):
        """Return recent local git commits for dashboard context."""
        try:
            result = subprocess.run(
                ['git', '--no-pager', 'log', '--since=today', '--oneline', '--decorate', f'-n{limit}'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(ROOT),
            )
            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(' ', 1)
                commit_id = parts[0]
                message = parts[1] if len(parts) > 1 else ''
                commits.append({
                    'id': commit_id,
                    'message': message,
                    'source': 'local-git',
                })
            return commits
        except Exception:
            return []

    @staticmethod
    def _get_recent_activity(limit=10):
        """Prefer public GitHub activity, then fall back to local git history."""
        github_activity = GitHubManager._get_public_github_activity(limit=limit)
        if github_activity:
            return github_activity
        return GitHubManager._get_recent_git_activity(limit=limit)

    @staticmethod
    def _get_workflow_runs(limit=10):
        """Fetch public GitHub workflow runs when available."""
        remote = GitHubManager._parse_github_remote()
        if not remote:
            return []

        try:
            runs = GitHubManager._github_api_get(
                f"/repos/{remote['owner']}/{remote['repo']}/actions/runs",
                {'per_page': limit},
            )
            workflow_runs = []
            for run in runs.get('workflow_runs', [])[:limit]:
                workflow_runs.append({
                    'id': run.get('id'),
                    'name': run.get('name') or run.get('display_title') or 'workflow-run',
                    'status': run.get('status'),
                    'conclusion': run.get('conclusion'),
                    'event': run.get('event'),
                    'head_branch': run.get('head_branch'),
                    'html_url': run.get('html_url'),
                    'updated_at': run.get('updated_at'),
                    'workflow_file': run.get('path', '').split('/')[-1] if run.get('path') else None,
                    'source': 'github-api',
                })
            return workflow_runs
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, json.JSONDecodeError):
            return []
    
    @staticmethod
    def get_github_status():
        """Check if .github/workflows exists and get workflow info."""
        try:
            gh_dir = ROOT / '.github' / 'workflows'
            recent_activity = GitHubManager._get_recent_activity()
            if not gh_dir.exists():
                return {
                    'status': 'not_configured',
                    'message': '.github/workflows directory not found',
                    'recent_git_activity': recent_activity,
                }
            
            workflows = []
            for wf_file in itertools.chain(gh_dir.glob('*.yml'), gh_dir.glob('*.yaml')):
                workflows.append({
                    'name': wf_file.name,
                    'path': str(wf_file.relative_to(ROOT)),
                    'size': wf_file.stat().st_size,
                })
            
            return {
                'status': 'configured',
                'workflows': workflows,
                'repository_root': str(ROOT),
                'recent_git_activity': recent_activity,
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'recent_git_activity': []}
    
    @staticmethod
    def get_github_actions_mock():
        """Mock GitHub Actions runs (since we can't auth without token)."""
        try:
            public_runs = GitHubManager._get_workflow_runs()
            recent_activity = GitHubManager._get_recent_activity()
            if public_runs:
                return {
                    'status': 'success',
                    'runs': public_runs,
                    'note': 'Public GitHub workflow runs loaded from the GitHub API',
                    'recent_git_activity': recent_activity,
                }

            # Read workflow files to show configuration
            gh_dir = ROOT / '.github' / 'workflows'
            if not gh_dir.exists():
                return {
                    'status': 'not_configured',
                    'runs': [],
                    'recent_git_activity': recent_activity,
                }
            
            runs = []
            for wf_file in itertools.chain(gh_dir.glob('*.yml'), gh_dir.glob('*.yaml')):
                content = wf_file.read_text(encoding='utf-8', errors='ignore')
                # Extract basic info
                runs.append({
                    'id': wf_file.stem,
                    'name': wf_file.stem,
                    'status': 'configured',
                    'workflow_file': wf_file.name,
                    'path': str(wf_file.relative_to(ROOT)),
                    'triggers': ['push', 'pull_request'] if 'push' in content.lower() else [],
                    'jobs': len([l for l in content.split('\n') if l.strip().startswith('- ')]),
                })
            
            return {
                'status': 'success',
                'runs': runs,
                'note': 'Workflow configurations loaded from .github/workflows',
                'recent_git_activity': recent_activity,
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'recent_git_activity': []}


class IntegrationStatus:
    """Overall integration status check."""
    
    @staticmethod
    def get_full_status():
        """Get integrated status of all DevOps components."""
        docker_status = DockerManager.get_containers()
        k8s_status = KubernetesManager.get_cluster_info()
        gh_status = GitHubManager.get_github_status()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'docker': docker_status,
            'kubernetes': k8s_status,
            'github': gh_status,
            'summary': {
                'docker_available': docker_status.get('status') == 'success',
                'kubernetes_connected': k8s_status.get('status') == 'connected',
                'github_configured': gh_status.get('status') == 'configured',
                'overall_health': 'healthy' if k8s_status.get('status') == 'connected' else 'degraded',
            }
        }
