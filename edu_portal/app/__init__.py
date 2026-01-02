from flask import Flask

from .config import SECRET_KEY
from .extensions import init_extensions
from .services import db_service


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../../templates", static_folder="../../static")
    app.secret_key = SECRET_KEY

    init_extensions(app)
    db_service.init_app(app)

    from .routes.auth import bp as auth_bp
    from .routes.student import bp as student_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)

    return app
