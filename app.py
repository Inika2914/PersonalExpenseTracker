import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager

from config import Config
from models import db
from models.user import User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Ensure the instance folder (where expenses.db lives) exists
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register one blueprint per module, matching the 4-module project structure
    from routes.auth import auth_bp
    from routes.analysis import analysis_bp
    from routes.transactions import transactions_bp
    from routes.api import api_bp
    from routes.capture import capture_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(capture_bp)

    # Root page: send visitors (including the Android app) to the login page
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    with app.app_context():
        db.create_all()   # creates tables from models if they don't exist yet
        from services.categorize import seed_default_categories
        seed_default_categories(db)

    return app


if __name__ == "__main__":
    app = create_app()
    # host="0.0.0.0" so a phone on the same WiFi (browser or the Android app) can reach it
    app.run(host="0.0.0.0", port=5000, debug=True)