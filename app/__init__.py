from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from config import Config

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'login'  # Redirect to 'login' route when login is required

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize app with extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Register Blueprints
    from app.routes import main
    app.register_blueprint(main)

    return app
