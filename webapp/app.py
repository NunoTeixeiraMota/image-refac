from pathlib import Path
from flask import Flask, send_from_directory

from .routes import api
from .utils import ensure_dirs, start_cleanup_thread


def create_app():
    base_dir = Path(__file__).resolve().parent.parent

    app = Flask(
        __name__,
        template_folder=str(base_dir / 'templates'),
        static_folder=str(base_dir / 'static'),
    )

    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max upload

    app.register_blueprint(api)

    @app.route('/')
    def index():
        return send_from_directory(str(base_dir / 'templates'), 'index.html')

    ensure_dirs()
    start_cleanup_thread()

    return app


def run(host='0.0.0.0', port=5000):
    from waitress import serve
    app = create_app()
    print(f'Image Converter running at http://localhost:{port}')
    serve(app, host=host, port=port)
