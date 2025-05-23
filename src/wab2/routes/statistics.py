from flask import Blueprint, render_template, request, session
from ..models import metrics_manager
import datetime

# Create the blueprint for statistics
bp = Blueprint('statistics', __name__, url_prefix='/statistics')

@bp.route('/')
def index():
    """Redirect to the individual statistics page by default."""
    return individual()

@bp.route('/individual')
def individual():
    """Render the individual agent statistics page."""
    # Get the current agent ID from session or use default
    agent_id = session.get('current_agent_id', 'default')
    
    # Get agent ID from query parameter if provided, otherwise use current agent
    selected_agent_id = request.args.get('agent_id', agent_id)
    
    # Get all available agent IDs for comparison
    agent_ids = metrics_manager.get_all_agent_ids()
    
    # Get metrics for this agent
    all_metrics = metrics_manager.get_all_metrics_by_agent(selected_agent_id)
    
    return render_template('statistics_individual.html',
                          agent_id=agent_id,
                          selected_agent_id=selected_agent_id,
                          agent_ids=agent_ids,
                          metrics=all_metrics,
                          current_year=datetime.datetime.now().year,
                          active_page="statistics_individual")

@bp.route('/overall')
def overall():
    """Render the overall statistics page with aggregated metrics."""
    # Get all available agent IDs
    agent_ids = metrics_manager.get_all_agent_ids()
    
    return render_template('statistics_overall.html',
                          agent_ids=agent_ids,
                          current_year=datetime.datetime.now().year,
                          active_page="statistics_overall")