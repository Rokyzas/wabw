from flask import Blueprint, render_template, session
from ..models import metrics_manager, global_settings
import datetime

# Create the blueprint for settings
bp = Blueprint('settings', __name__, url_prefix='/settings')

@bp.route('/')
def index():
    """Render the settings page."""
    # Get the current agent ID from session or use default
    agent_id = session.get('current_agent_id', 'default')
    
    # Get all available agent IDs
    agent_ids = metrics_manager.get_all_agent_ids()
    
    # Get global settings
    all_global_settings = global_settings.get_all_settings()
    
    # Format the last_updated timestamp if it exists
    if all_global_settings.get('last_updated'):
        try:
            # Parse ISO format date and convert to more readable format
            dt = datetime.datetime.fromisoformat(all_global_settings['last_updated'])
            all_global_settings['last_updated'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            # If parsing fails, leave as is
            pass
    
    return render_template('settings.html',
                          agent_id=agent_id,
                          agent_ids=agent_ids,
                          global_settings=all_global_settings,
                          current_year=datetime.datetime.now().year,
                          active_page="settings") 