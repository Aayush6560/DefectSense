import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix


def create_app():
    root = os.path.dirname(os.path.abspath(__file__))

    app = Flask(
        __name__,
        template_folder=root,
        static_folder=root,
    )

    secret = os.environ.get('SECRET_KEY', '').strip()
    if not secret:
        secret = 'defectsense-dev-secret-change-me'
        if os.environ.get('FLASK_ENV') == 'production':
            app.logger.warning('[SECURITY] SECRET_KEY not set in environment. Using fallback dev key. Set SECRET_KEY in production.')

    app.config['SECRET_KEY'] = secret
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    app.config['JSON_SORT_KEYS'] = False

    allowed_origins_raw = os.environ.get('ALLOWED_ORIGINS', '*')
    allowed_origins = [o.strip() for o in allowed_origins_raw.split(',') if o.strip()]
    # Use Flask-CORS for basic handling, but also ensure credentials and origin echoing
    CORS(app, origins=allowed_origins or ['*'], supports_credentials=True)

    # If the app is behind a reverse proxy (NGINX ingress), honor forwarded headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.after_request
    def _ensure_cors_credentials(resp):
        # Ensure credentialed CORS responses echo the request origin when '*' is used
        # Import `request` locally to avoid any module-level shadowing or import-order issues
        from flask import request as _fl_request
        origin = _fl_request.headers.get('Origin')
        if origin:
            if '*' in allowed_origins or allowed_origins == ['*']:
                resp.headers['Access-Control-Allow-Origin'] = origin
            elif origin in allowed_origins:
                resp.headers['Access-Control-Allow-Origin'] = origin
        # Always allow credentials when configured
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        return resp

    logging.basicConfig(
        level=logging.DEBUG if os.environ.get('FLASK_ENV') != 'production' else logging.WARNING,
        format='[%(asctime)s] %(levelname)s %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    try:
        from routes import main
        app.register_blueprint(main)
    except ImportError as e:
        app.logger.error(f'[STARTUP] Failed to load routes blueprint: {e}')
        raise

    try:
        from dashboard import dashboard_bp
        app.register_blueprint(dashboard_bp)
    except ImportError as e:
        app.logger.error(f'[STARTUP] Failed to load dashboard blueprint: {e}')
        raise

    try:
        from auth_routes import auth_bp
        app.register_blueprint(auth_bp)
    except ImportError as e:
        app.logger.error(f'[STARTUP] Failed to load auth blueprint: {e}')
        raise

    @app.route('/health')
    def health():
        from ml.predict import is_model_loaded, get_model_meta
        model_ready = is_model_loaded()
        meta = get_model_meta()
        return jsonify({
            'status': 'ok',
            'model_loaded': model_ready,
            'model': meta.get('selected_model', 'unknown'),
            'auc_roc': meta.get('auc_roc'),
            'threshold': meta.get('decision_threshold'),
            'version': '1.0.0',
        }), 200

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({'error': 'Bad request', 'message': str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Not found', 'message': str(e)}), 404

    @app.errorhandler(413)
    def file_too_large(e):
        return jsonify({'error': 'File too large', 'message': 'Maximum upload size is 5MB'}), 413

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f'[500] Internal error: {e}')
        return jsonify({'error': 'Internal server error', 'message': 'Something went wrong on the server'}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        app.logger.exception(f'[UNHANDLED] {type(e).__name__}: {e}')
        return jsonify({'error': 'Unexpected error', 'message': str(e)}), 500

    return app