from flask import Flask
from .models.task import load_all_tasks
from .models import task_state_manager, metrics_manager, global_settings
import os

def create_app():
    app = Flask(__name__)
    
    # Set a secret key for sessions
    app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_wab2_please_change_in_production')
    
    # Initialize task state manager
    task_state_manager.initialize()
    
    # Initialize metrics manager
    metrics_manager.initialize()
    
    # Initialize global settings
    global_settings.initialize()
    
    # Load all tasks at startup
    load_all_tasks()
    
    # Register routes
    from .routes import tasks, api, home, settings, statistics
    app.register_blueprint(home.bp, url_prefix='')  # Make home the root route
    app.register_blueprint(tasks.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(statistics.bp)
    app.register_blueprint(api.api)
    
    return app
