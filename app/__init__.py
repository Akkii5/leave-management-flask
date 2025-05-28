from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from config import Config

# Initialize Flask extensions globally
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
login_manager = LoginManager()

# Specify the login view for @login_required redirects
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'warning'  # For flashed messages

def create_app():
    # Create the Flask app instance
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize the app with Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Import and register blueprints
    from app.routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app