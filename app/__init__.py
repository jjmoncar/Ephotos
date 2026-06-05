import os
import sys
import logging

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from logging.handlers import RotatingFileHandler
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address, storage_uri=os.getenv("REDIS_URL", "redis://localhost:6379/0"))

def setup_logging(app):
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    
    setup_logging(app)

    with app.app_context():
        from app.routes import upload, admin
        app.register_blueprint(upload.bp)
        app.register_blueprint(admin.bp)
        
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('admin.dashboard'))
        
    return app
