from flask import Blueprint, render_template, session
import datetime

# Create the blueprint for the home page
bp = Blueprint('home', __name__)

@bp.route('/')
def index():
    """Render the home page with project description and instructions."""
    # Get the current agent ID from session or use default
    agent_id = session.get('current_agent_id', 'default')
    
    return render_template('home.html', 
                          current_year=datetime.datetime.now().year,
                          active_page="home",
                          agent_id=agent_id)