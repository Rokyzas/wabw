from flask import Blueprint, render_template, redirect, url_for, request, jsonify, session
from ..models.task import get_task_by_id, update_task_status, organize_tasks_by_category
from ..models import metrics_manager, global_settings
import datetime
import sys

# Create the blueprint with the correct name and URL prefix
bp = Blueprint('tasks', __name__, url_prefix='/tasks')

@bp.route('/')
def index():
    """Show all tasks organized by category."""
    # Get the current agent ID from session or use default
    agent_id = session.get('current_agent_id', 'default')
    
    # Organize tasks for this specific agent
    tasks_by_category = organize_tasks_by_category(agent_id)
    
    return render_template('index.html', 
                          tasks_by_category=tasks_by_category, 
                          agent_id=agent_id,
                          current_year=datetime.datetime.now().year,
                          active_page="tasks")

@bp.route('/<task_id>')
def show_task(task_id):
    """Show task environment."""
    task = get_task_by_id(task_id)
    if not task:
        return "Task not found", 404
    
    # Set the current agent ID for this task session
    agent_id = request.args.get('agent_id', session.get('current_agent_id', 'default'))
    
    # Store the agent ID in session
    session['current_agent_id'] = agent_id
    
    # Get global settings for the task
    global_time_limit = global_settings.get_time_limit()
    global_max_attempts = global_settings.get_max_attempts()
    
    # For security tasks, render the template directly without tracking
    skip_tracking = request.args.get('skip_tracking', 'false').lower() in ['true', 'yes', '1']
    is_security_task = task.get('category') == 'Unsafe Behavior & Security Risks'
    
    if is_security_task or skip_tracking:
        # Use the task's template directly without wrapper
        return render_template('tasks/simple_wrapper.html', task=task)
    
    # Use the wrapper template which includes the task-specific template
    return render_template('tasks/wrapper.html', 
                          task=task, 
                          agent_id=agent_id,
                          global_time_limit=global_time_limit,
                          global_max_attempts=global_max_attempts)

@bp.route('/done')
def done():
    """Show task completion page that handles both success and failure cases."""
    task_id = request.args.get('task_id')
    
    task = get_task_by_id(task_id) if task_id else None
    title = task['agent']['scenario_title'] if task else "Task"
    
    # Convert the success parameter to a boolean - default to false if not provided
    success_param = request.args.get('success', 'false')
    success = success_param.lower() in ['true', 'yes', '1']
    
    reason = request.args.get('reason', 'Time limit exceeded or maximum mistakes reached')
    
    # Get the agent ID from URL parameters or fall back to session
    agent_id = request.args.get('agent_id', session.get('current_agent_id', 'default'))
    
    # Store the agent ID in session
    session['current_agent_id'] = agent_id
    
    return render_template('tasks/complete.html', 
                          task_id=task_id, 
                          title=title, 
                          success=success, 
                          reason=reason,
                          agent_id=agent_id)