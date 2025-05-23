from flask import Blueprint, jsonify, request, url_for, session, make_response
from ..models.task import get_task_by_id, update_task_status, organize_tasks_by_category, load_all_tasks
from ..models import task_state_manager, metrics_manager, global_settings
import time
from datetime import datetime
import json

# Simple console log function
def console_log(message):
    print(f"[API] {message}")

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/tasks', methods=['GET'])
def list_tasks():
    """Get all available tasks organized by category."""
    # Get the current agent from query params or session
    agent_id = request.args.get('agent_id', session.get('current_agent_id', 'default'))
    
    # Load tasks with states for this specific agent
    load_all_tasks(agent_id)
    
    # Organize tasks by category for this agent
    organized_tasks = organize_tasks_by_category(agent_id)
    
    return jsonify(organized_tasks)

@api.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id: str):
    """Get details of a specific task."""
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)

@api.route('/tasks/start', methods=['POST'])
def start_task():
    """Start a new task session."""
    data = request.get_json()
    task_id = data.get('task_id')
    task_url = data.get('task_url')
    agent_id = data.get('agent_id', 'default')
    
    if not task_id or not task_url:
        return jsonify({"error": "Task ID and URL are required"}), 400
        
    task = get_task_by_id(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    # Check if there are existing metrics for this agent on this task
    metrics = metrics_manager.get_task_metrics_for_agent(task_id, agent_id)
    if metrics:
        # If same agent already has metrics for this task, reset them
        metrics_manager.reset_task_metrics(task_id, agent_id)
        console_log(f"Resetting existing metrics for agent {agent_id} on task {task_id}")
    else:
        console_log(f"Creating new metrics for agent {agent_id} on task {task_id}")
        
    # Initialize new metrics
    metrics_manager.update_task_metrics(
        task_id=task_id,
        status='in_progress',
        agent_id=agent_id,
        start_time=datetime.now().isoformat()
    )
    
    return jsonify({
        'task_id': task_id,
        'task_url': task_url,
        'status': 'started',
        'agent_id': agent_id
    })

@api.route('/log_action', methods=['POST'])
def log_action():
    """Log an action taken during a task."""
    data = request.get_json()
    task_id = data.get('task_id')
    action = data.get('action')
    element = data.get('element', '')
    value = data.get('value', '')
    agent_id = data.get('agent_id', 'default')

    if not task_id or not action:
        return jsonify({'error': 'Missing required fields'}), 400

    # Log the action using the metrics manager
    action_count = metrics_manager.log_action(
        task_id=task_id,
        action=action,
        element=element,
        value=value,
        agent_id=agent_id
    )

    return jsonify({'success': True, 'action_count': action_count})

@api.route('/check_success', methods=['POST'])
def check_success():
    """Check if the task has met its success criteria.
    This endpoint should NOT determine task-specific success.
    Instead, task templates should call window.completeTask(true) when success is achieved.
    This endpoint only returns analytics data and tracks mistakes."""
    data = request.get_json()
    task_id = data.get('task_id')

    if not task_id:
        return jsonify({'error': 'Missing task_id'}), 400

    task = get_task_by_id(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404

    # Get task metrics
    metrics = metrics_manager.get_task_metrics(task_id)
    
    # Default settings if not specified in task
    # Note: We use 'max_attempts' field from task files but represent it as 'mistakes' in our logic
    max_mistakes = task.get('settings', {}).get('max_attempts', 3)
    
    # Return current metrics data - don't determine success here
    # Task templates should call window.completeTask(true) when task-specific success is achieved
    return jsonify({
        'action_count': len(metrics.get('actions', [])),
        'mistakes': metrics.get('mistakes', 0),
        'max_mistakes': max_mistakes,
        'success': False  # Leave success determination to task templates
    })

@api.route('/tasks/complete', methods=['POST'])
def complete_task():
    """Mark a task as completed and record results."""
    data = request.get_json()
    task_id = data.get('session_id')  # Using session_id as task_id for backward compatibility
    if not task_id:
        task_id = data.get('task_id')
    
    success = data.get('success', False)
    notes = data.get('notes', '')
    agent_id = data.get('agent_id', session.get('current_agent_id', 'default'))

    if not task_id:
        return jsonify({'error': 'Missing task_id'}), 400

    # Get task details
    task = get_task_by_id(task_id)
        
    # Update task status in task state manager for this agent
    status = 'completed' if success else 'failed'

    update_task_status(task_id, status, agent_id)
    
    metrics = metrics_manager.complete_task(
        task_id=task_id,
        success=success,
        notes=notes,
        agent_id=agent_id
    )
    
    # Redirect to appropriate page with success parameter
    redirect_url = url_for('tasks.done', task_id=task_id, success=str(success).lower(), agent_id=agent_id)
    if not success:
        # Add reason parameter if task failed
        # Use global max attempts setting
        max_mistakes = global_settings.get_max_attempts()
        if metrics.get('mistakes', 0) >= max_mistakes:
            redirect_url += "&reason=Maximum%20mistakes%20reached"
        else:
            redirect_url += "&reason=Time%20limit%20exceeded"
    
    return jsonify({
        'status': status,
        'success': success,
        'duration': metrics.get('duration', 0),
        'action_count': len(metrics.get('actions', [])),
        'mistakes': metrics.get('mistakes', 0),
        'redirect_url': redirect_url
    })

@api.route('/tasks/metrics/<task_id>', methods=['GET'])
def get_task_metrics(task_id):
    """Get metrics for a specific task."""
    metrics = metrics_manager.get_task_metrics(task_id)
    if not metrics:
        return jsonify({'error': 'No metrics found for this task'}), 404
        
    return jsonify(metrics)

@api.route('/record_mistake', methods=['POST'])
def record_mistake():
    """Record a mistake for a task."""
    data = request.get_json()
    task_id = data.get('task_id')
    mistake_type = data.get('type', 'unspecified')
    details = data.get('details', '')
    agent_id = data.get('agent_id', session.get('current_agent_id', 'default'))
    
    if not task_id:
        return jsonify({'error': 'Missing task_id'}), 400
        
    # Get task to check mistake limit
    task = get_task_by_id(task_id)
    
    # Update mistake count in metrics
    mistake_count = metrics_manager.record_mistake(
        task_id=task_id,
        mistake_type=mistake_type,
        details=details,
        agent_id=agent_id
    )
    
    # Use global max attempts setting
    max_mistakes = global_settings.get_max_attempts()
    
    # Check if max mistakes reached
    max_mistakes_reached = mistake_count >= max_mistakes
    
    return jsonify({
        'success': True,
        'mistakes': mistake_count,
        'max_mistakes': max_mistakes,
        'max_mistakes_reached': max_mistakes_reached
    })

@api.route('/tasks/reset_all', methods=['POST'])
def reset_all_task_metrics():
    """Reset all task metrics and statuses for a specific agent."""
    data = request.get_json() or {}
    agent_id = data.get('agent_id', session.get('current_agent_id', 'default'))
    
    # Reset metrics using the metrics manager
    metrics_manager.reset_all_metrics(agent_id)
    
    # Reset task states for this specific agent
    task_state_manager.reset_all_task_states(agent_id)
    
    # Reload tasks to apply the reset statuses
    load_all_tasks(agent_id)
        
    return jsonify({
        'success': True,
        'message': f'All task metrics and statuses reset successfully for agent {agent_id}'
    })

@api.route('/tasks/export', methods=['POST'])
def export_metrics_file():
    """Export task metrics to a file for a specific agent."""
    data = request.get_json()
    agent_id = data.get('agent_id', 'default')
    
    # Use the metrics manager to export
    result = metrics_manager.export_metrics_to_file(agent_id)
    
    return jsonify(result)

@api.route('/tasks/aggregate', methods=['GET'])
def get_aggregate_results():
    """Get aggregated results across all tasks."""
    agent_id = request.args.get('agent_id', 'current')
    
    # Get metrics for this agent
    if agent_id == 'all':
        # Get all metrics, flattened
        metrics = metrics_manager.get_all_metrics()
    elif agent_id == 'current':
        # Use the current agent from session
        current_agent = session.get('current_agent_id', 'default')
        metrics_by_task = metrics_manager.get_all_metrics_by_agent(current_agent)
        
        # Flatten metrics
        metrics = {}
        for task_id, task_metrics in metrics_by_task.items():
            metrics[task_id] = task_metrics
    else:
        # Get metrics for specific agent
        metrics_by_task = metrics_manager.get_all_metrics_by_agent(agent_id)
        
        # Flatten metrics
        metrics = {}
        for task_id, task_metrics in metrics_by_task.items():
            metrics[task_id] = task_metrics
    
    if not metrics:
        return jsonify({'error': f'No metrics found for agent {agent_id}'}), 404
    
    # Aggregate the results
    aggregate = {
        'agent_id': agent_id if agent_id != 'current' else session.get('current_agent_id', 'default'),
        'total_tasks': len(metrics),
        'completed_tasks': sum(1 for m in metrics.values() if m.get('status') == 'completed'),
        'failed_tasks': sum(1 for m in metrics.values() if m.get('status') == 'failed'),
        'success_rate': sum(1 for m in metrics.values() if m.get('success', False)) / len(metrics) if metrics else 0,
        'average_duration': sum(m.get('duration', 0) for m in metrics.values() if 'duration' in m) / len(metrics) if metrics else 0,
        'average_mistakes': sum(m.get('mistakes', 0) for m in metrics.values()) / len(metrics) if metrics else 0,
        'average_actions': sum(len(m.get('actions', [])) for m in metrics.values()) / len(metrics) if metrics else 0,
        'categories': {}
    }
    
    # Aggregate by category
    for task_id, metric in metrics.items():
        task = get_task_by_id(task_id)
        if not task:
            continue
            
        category = task.get('category', 'Unknown')
        if category not in aggregate['categories']:
            aggregate['categories'][category] = {
                'total': 0,
                'completed': 0,
                'success_rate': 0,
                'average_duration': 0,
                'average_mistakes': 0
            }
        
        # Update category stats
        cat_stats = aggregate['categories'][category]
        cat_stats['total'] += 1
        if metric.get('status') == 'completed':
            cat_stats['completed'] += 1
        cat_stats['success_rate'] = sum(1 for m in metrics.values() 
                                      if get_task_by_id(m.get('task_id', task_id)) 
                                      and get_task_by_id(m.get('task_id', task_id)).get('category') == category 
                                      and m.get('success', False)) / cat_stats['total']
                                      
        # Add duration and mistakes for averages
        cat_stats['average_duration'] += metric.get('duration', 0)
        cat_stats['average_mistakes'] += metric.get('mistakes', 0)
    
    # Calculate averages for categories
    for category, stats in aggregate['categories'].items():
        if stats['total'] > 0:
            stats['average_duration'] /= stats['total']
            stats['average_mistakes'] /= stats['total']
    
    return jsonify(aggregate)

# Export endpoints
@api.route('/export/actions', methods=['GET'])
def export_actions():
    """Export raw action data for tasks."""
    agent_id = request.args.get('agent_id', 'all')
    format_type = request.args.get('format', 'json')
    
    if agent_id == 'all':
        # For all agents, use flattened metrics
        metrics = metrics_manager.get_all_metrics()
    else:
        # For specific agent, get only their metrics
        metrics_by_task = metrics_manager.get_all_metrics_by_agent(agent_id)
        
        # Flatten metrics
        metrics = {}
        for task_id, task_metrics in metrics_by_task.items():
            metrics[task_id] = task_metrics
    
    if not metrics:
        return jsonify({'error': 'No metrics found for the specified agent(s)'}), 404
    
    # Extract raw actions data
    actions_data = {}
    
    # Group by agent ID
    for task_id, task_metrics in metrics.items():
        agent_id = task_metrics.get('agent_id', 'default')
        
        if agent_id not in actions_data:
            actions_data[agent_id] = {}
            
        if 'actions' in task_metrics:
            # Get task name for better context
            task = get_task_by_id(task_id)
            task_name = task['agent']['scenario_title'] if task else task_id
            
            actions_data[agent_id][task_id] = {
                'task_name': task_name,
                'actions': task_metrics['actions']
            }
    
    # Format output based on requested format
    if format_type == 'csv':
        # Generate CSV
        import csv
        from io import StringIO
        
        output = StringIO()
        csv_writer = csv.writer(output)
        
        # Write header
        csv_writer.writerow(['agent_id', 'task_id', 'task_name', 'action_index', 
                             'timestamp', 'action_type', 'element', 'value'])
        
        # Write data
        for aid, agent_data in actions_data.items():
            for task_id, task_data in agent_data.items():
                task_name = task_data['task_name']
                for i, action in enumerate(task_data['actions']):
                    csv_writer.writerow([
                        aid,
                        task_id,
                        task_name,
                        i + 1,
                        action.get('timestamp', ''),
                        action.get('action', ''),
                        action.get('element', ''),
                        action.get('value', '')
                    ])
        
        return output.getvalue(), 200, {'Content-Type': 'text/csv'}
    else:
        # Return JSON format
        return jsonify(actions_data)

@api.route('/export/metrics', methods=['GET'])
def export_task_metrics():
    """Export task metrics data."""
    agent_id = request.args.get('agent_id', 'all')
    format_type = request.args.get('format', 'json')
    
    if agent_id == 'all':
        # For all agents, get all metrics structured by tasks and agents
        all_metrics = metrics_manager.task_metrics
        
        # Convert to the expected format for output
        metrics_data = {}
        for task_id, agents in all_metrics.items():
            for aid, task_metrics in agents.items():
                if aid not in metrics_data:
                    metrics_data[aid] = {}
                    
                # Get task name for better context
                task = get_task_by_id(task_id)
                task_name = task['agent']['scenario_title'] if task else task_id
                category = task['category'] if task else 'Unknown'
                
                # Create a clean metrics object without raw actions
                clean_metrics = {
                    'task_name': task_name,
                    'category': category,
                    'status': task_metrics.get('status', 'unknown'),
                    'success': task_metrics.get('success', False),
                    'duration': task_metrics.get('duration', 0),
                    'mistakes': task_metrics.get('mistakes', 0),
                    'action_count': len(task_metrics.get('actions', [])),
                    'start_time': task_metrics.get('start_time', ''),
                    'end_time': task_metrics.get('end_time', '')
                }
                
                metrics_data[aid][task_id] = clean_metrics
    else:
        # For specific agent, get only their metrics
        metrics_by_task = metrics_manager.get_all_metrics_by_agent(agent_id)
        
        if not metrics_by_task:
            return jsonify({'error': f'No metrics found for agent {agent_id}'}), 404
            
        # Convert to the expected format for output
        metrics_data = {agent_id: {}}
        for task_id, task_metrics in metrics_by_task.items():
            # Get task name for better context
            task = get_task_by_id(task_id)
            task_name = task['agent']['scenario_title'] if task else task_id
            category = task['category'] if task else 'Unknown'
            
            # Create a clean metrics object without raw actions
            clean_metrics = {
                'task_name': task_name,
                'category': category,
                'status': task_metrics.get('status', 'unknown'),
                'success': task_metrics.get('success', False),
                'duration': task_metrics.get('duration', 0),
                'mistakes': task_metrics.get('mistakes', 0),
                'action_count': len(task_metrics.get('actions', [])),
                'start_time': task_metrics.get('start_time', ''),
                'end_time': task_metrics.get('end_time', '')
            }
            
            metrics_data[agent_id][task_id] = clean_metrics
    
    if not metrics_data:
        return jsonify({'error': 'No metrics found for the specified agent(s)'}), 404
    
    # Format output based on requested format
    if format_type == 'csv':
        # Generate CSV
        import csv
        from io import StringIO
        
        output = StringIO()
        csv_writer = csv.writer(output)
        
        # Write header
        csv_writer.writerow(['agent_id', 'task_id', 'task_name', 'category', 'status', 
                             'success', 'duration', 'mistakes', 'action_count', 
                             'start_time', 'end_time'])
        
        # Write data
        for aid, agent_data in metrics_data.items():
            for task_id, metrics in agent_data.items():
                csv_writer.writerow([
                    aid,
                    task_id,
                    metrics['task_name'],
                    metrics['category'],
                    metrics['status'],
                    'Yes' if metrics['success'] else 'No',
                    metrics['duration'],
                    metrics['mistakes'],
                    metrics['action_count'],
                    metrics['start_time'],
                    metrics['end_time']
                ])
        
        return output.getvalue(), 200, {'Content-Type': 'text/csv'}
    else:
        # Return JSON format
        return jsonify(metrics_data)

@api.route('/export/summary', methods=['GET'])
def export_summary():
    """Export summary report with aggregate statistics."""
    agent_id = request.args.get('agent_id', 'all')
    format_type = request.args.get('format', 'json')
    
    # Get all metrics in the raw nested structure
    all_metrics = metrics_manager.task_metrics
    
    # Prepare a summary by agent
    summary = {
        'generated_at': datetime.now().isoformat(),
        'agents': {}
    }
    
    # Get all agent IDs from metrics
    agent_ids = metrics_manager.get_all_agent_ids() if agent_id == 'all' else [agent_id]
    
    for aid in agent_ids:
        # Extract metrics for this agent
        agent_metrics = {}
        for task_id, agents in all_metrics.items():
            if aid in agents:
                agent_metrics[task_id] = agents[aid]
        
        if not agent_metrics:
            continue
        
        # Calculate agent-level stats
        total_tasks = len(agent_metrics)
        completed_tasks = sum(1 for m in agent_metrics.values() if m.get('status') == 'completed')
        successful_tasks = sum(1 for m in agent_metrics.values() if m.get('success', False))
        failed_tasks = sum(1 for m in agent_metrics.values() if m.get('status') == 'failed')
        
        success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0
        avg_duration = sum(m.get('duration', 0) for m in agent_metrics.values() if 'duration' in m) / total_tasks if total_tasks > 0 else 0
        avg_mistakes = sum(m.get('mistakes', 0) for m in agent_metrics.values()) / total_tasks if total_tasks > 0 else 0
        total_actions = sum(len(m.get('actions', [])) for m in agent_metrics.values())
        avg_actions = total_actions / total_tasks if total_tasks > 0 else 0
        
        # Organize by category
        categories = {}
        for task_id, metric in agent_metrics.items():
            task = get_task_by_id(task_id)
            if not task:
                continue
                
            category = task.get('category', 'Unknown')
            if category not in categories:
                categories[category] = {
                    'total': 0,
                    'completed': 0,
                    'successful': 0,
                    'failed': 0,
                    'total_duration': 0,
                    'total_mistakes': 0,
                    'total_actions': 0
                }
            
            # Update category stats
            cat_stats = categories[category]
            cat_stats['total'] += 1
            if metric.get('status') == 'completed':
                cat_stats['completed'] += 1
            if metric.get('success', False):
                cat_stats['successful'] += 1
            if metric.get('status') == 'failed':
                cat_stats['failed'] += 1
                
            cat_stats['total_duration'] += metric.get('duration', 0)
            cat_stats['total_mistakes'] += metric.get('mistakes', 0)
            cat_stats['total_actions'] += len(metric.get('actions', []))
        
        # Calculate averages and percentages for categories
        category_summaries = {}
        for category, stats in categories.items():
            if stats['total'] > 0:
                category_summaries[category] = {
                    'total_tasks': stats['total'],
                    'completion_rate': stats['completed'] / stats['total'],
                    'success_rate': stats['successful'] / stats['total'],
                    'failure_rate': stats['failed'] / stats['total'],
                    'avg_duration': stats['total_duration'] / stats['total'],
                    'avg_mistakes': stats['total_mistakes'] / stats['total'],
                    'avg_actions': stats['total_actions'] / stats['total']
                }
        
        # Store agent summary
        summary['agents'][aid] = {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'successful_tasks': successful_tasks,
            'failed_tasks': failed_tasks,
            'success_rate': success_rate,
            'avg_duration': avg_duration,
            'avg_mistakes': avg_mistakes,
            'total_actions': total_actions,
            'avg_actions': avg_actions,
            'categories': category_summaries
        }
    
    # Format output based on requested format
    if format_type == 'csv':
        # CSV generation code remains the same
        import csv
        from io import StringIO
        
        output = StringIO()
        csv_writer = csv.writer(output)
        
        # Write agent summary header
        csv_writer.writerow([
            'Agent ID', 'Total Tasks', 'Completed Tasks', 'Successful Tasks', 
            'Failed Tasks', 'Success Rate', 'Avg Duration (s)', 
            'Avg Mistakes', 'Total Actions', 'Avg Actions'
        ])
        
        # Write agent summaries
        for aid, agent_data in summary['agents'].items():
            csv_writer.writerow([
                aid,
                agent_data['total_tasks'],
                agent_data['completed_tasks'],
                agent_data['successful_tasks'],
                agent_data['failed_tasks'],
                f"{agent_data['success_rate']:.2f}",
                f"{agent_data['avg_duration']:.2f}",
                f"{agent_data['avg_mistakes']:.2f}",
                agent_data['total_actions'],
                f"{agent_data['avg_actions']:.2f}"
            ])
        
        # Add blank row between sections
        csv_writer.writerow([])
        
        # Write category summary header
        csv_writer.writerow([
            'Agent ID', 'Category', 'Total Tasks', 'Completion Rate', 
            'Success Rate', 'Failure Rate', 'Avg Duration (s)', 
            'Avg Mistakes', 'Avg Actions'
        ])
        
        # Write category summaries
        for aid, agent_data in summary['agents'].items():
            for category, cat_data in agent_data['categories'].items():
                csv_writer.writerow([
                    aid,
                    category,
                    cat_data['total_tasks'],
                    f"{cat_data['completion_rate']:.2f}",
                    f"{cat_data['success_rate']:.2f}",
                    f"{cat_data['failure_rate']:.2f}",
                    f"{cat_data['avg_duration']:.2f}",
                    f"{cat_data['avg_mistakes']:.2f}",
                    f"{cat_data['avg_actions']:.2f}"
                ])
        
        return output.getvalue(), 200, {'Content-Type': 'text/csv'}
    else:
        # Return JSON format
        return jsonify(summary)

@api.route('/tasks/agents', methods=['GET'])
def list_agent_ids():
    """List all available agent IDs."""
    agent_ids = metrics_manager.get_all_agent_ids()
    return jsonify({"agent_ids": agent_ids})

@api.route('/tasks/set_agent', methods=['POST'])
def set_agent():
    """Save the current agent ID in the session."""
    data = request.get_json()
    agent_id = data.get('agent_id', 'default')
    
    # Store in session
    session['current_agent_id'] = agent_id
    
    return jsonify({
        'success': True,
        'agent_id': agent_id
    })

@api.route('/tasks/current_agent', methods=['GET'])
def get_current_agent():
    """Get the current agent ID from the session."""
    agent_id = session.get('current_agent_id', 'default')
    
    return jsonify({
        'agent_id': agent_id
    })

@api.route('/debug/metrics', methods=['GET'])
def debug_metrics():
    """Debug endpoint to show the current metrics."""
    # Only enable in development
    if request.args.get('key') != 'debug_wab2':
        return jsonify({'error': 'Unauthorized'}), 403
        
    # Get all metrics from the metrics manager in the nested structure
    all_metrics = metrics_manager.task_metrics
    
    # Count total task-agent combinations
    total_combinations = sum(len(agents) for agents in all_metrics.values())
    
    result = {
        'task_count': len(all_metrics),
        'task_agent_combinations': total_combinations,
        'all_agent_ids': metrics_manager.get_all_agent_ids(),
        'tasks': {}
    }
    
    # Process metrics for each task and agent
    for task_id, agents in all_metrics.items():
        task = get_task_by_id(task_id)
        task_name = task['agent']['scenario_title'] if task else 'Unknown'
        
        # Create an entry for this task with data for each agent
        result['tasks'][task_id] = {
            'name': task_name,
            'agents': {}
        }
        
        # Add data for each agent
        for agent_id, metrics in agents.items():
            result['tasks'][task_id]['agents'][agent_id] = {
                'status': metrics.get('status', 'unknown'),
                'action_count': len(metrics.get('actions', [])),
                'mistakes': metrics.get('mistakes', 0),
                'success': metrics.get('success', False),
                'duration': metrics.get('duration', 0) if 'duration' in metrics else 'N/A'
            }
    
    return jsonify(result)

@api.route('/settings/update', methods=['POST'])
def update_settings():
    """Update global settings."""
    data = request.get_json()
    
    # Validate required fields
    if not data:
        return jsonify({'error': 'Missing request data'}), 400
    
    # Extract settings from request
    new_settings = {}
    
    # Time limit validation
    if 'time_limit_sec' in data:
        time_limit = int(data['time_limit_sec'])
        if time_limit < 10 or time_limit > 300:
            return jsonify({'error': 'Time limit must be between 10 and 300 seconds'}), 400
        new_settings['time_limit_sec'] = time_limit
        
    # Max attempts validation
    if 'max_attempts' in data:
        max_attempts = int(data['max_attempts'])
        if max_attempts < 1 or max_attempts > 10:
            return jsonify({'error': 'Max attempts must be between 1 and 10'}), 400
        new_settings['max_attempts'] = max_attempts
    
    # Update settings
    success = global_settings.update_settings(new_settings)
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Settings updated successfully',
            'settings': global_settings.get_all_settings()
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to update settings'
        }), 500

@api.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get leaderboard data comparing all agent performance."""
    # Get all agent IDs
    agent_ids = metrics_manager.get_all_agent_ids()
    
    # Get type of sorting (what metric to sort by)
    sort_by = request.args.get('sort_by', 'success_rate')
    valid_sort_fields = ['success_rate', 'average_duration', 'average_mistakes', 'average_actions']
    
    if sort_by not in valid_sort_fields:
        sort_by = 'success_rate'
    
    # Collect data for all agents
    leaderboard_data = []
    
    for agent_id in agent_ids:
        # Skip the 'all' special case
        if agent_id == 'all':
            continue
            
        # Get metrics for this agent
        metrics_by_task = metrics_manager.get_all_metrics_by_agent(agent_id)
        
        if not metrics_by_task:
            continue
            
        # Calculate aggregated metrics
        task_count = len(metrics_by_task)
        completed_count = sum(1 for m in metrics_by_task.values() if m.get('status') == 'completed')
        success_count = sum(1 for m in metrics_by_task.values() if m.get('success', False))
        
        if task_count > 0:
            success_rate = success_count / task_count
            avg_duration = sum(m.get('duration', 0) for m in metrics_by_task.values() if 'duration' in m) / task_count
            avg_mistakes = sum(m.get('mistakes', 0) for m in metrics_by_task.values()) / task_count
            avg_actions = sum(len(m.get('actions', [])) for m in metrics_by_task.values()) / task_count
            
            leaderboard_data.append({
                'agent_id': agent_id,
                'task_count': task_count,
                'completed_count': completed_count,
                'success_count': success_count,
                'success_rate': success_rate,
                'average_duration': avg_duration,
                'average_mistakes': avg_mistakes,
                'average_actions': avg_actions
            })
    
    # Sort by the specified field
    reverse = True if sort_by == 'success_rate' else False
    leaderboard_data.sort(key=lambda x: x[sort_by], reverse=reverse)
    
    return jsonify({
        'sort_by': sort_by,
        'leaderboard': leaderboard_data
    })

@api.route('/benchmark_summary', methods=['GET'])
def get_benchmark_summary():
    """Get summary statistics for the entire benchmark."""
    # Get all agent IDs
    agent_ids = metrics_manager.get_all_agent_ids()
    
    # Filter out special cases
    agent_ids = [aid for aid in agent_ids if aid != 'all']
    
    # Get task list
    from ..models.task import load_all_tasks
    all_tasks = load_all_tasks()
    total_tasks = len(all_tasks)
    
    # Calculate aggregate metrics
    total_success = 0
    total_agents_with_metrics = 0
    agent_success_rates = {}
    
    for agent_id in agent_ids:
        # Get metrics for this agent
        metrics_by_task = metrics_manager.get_all_metrics_by_agent(agent_id)
        
        if metrics_by_task:
            total_agents_with_metrics += 1
            task_count = len(metrics_by_task)
            success_count = sum(1 for m in metrics_by_task.values() if m.get('success', False))
            
            if task_count > 0:
                success_rate = success_count / task_count
                agent_success_rates[agent_id] = success_rate
                total_success += success_rate
    
    # Calculate average success rate across all agents
    average_success_rate = 0
    if total_agents_with_metrics > 0:
        average_success_rate = total_success / total_agents_with_metrics
    
    # Find best performing agent
    best_agent = max(agent_success_rates.items(), key=lambda x: x[1])[0] if agent_success_rates else "None"
    
    return jsonify({
        'total_tasks': total_tasks,
        'total_agents': total_agents_with_metrics,
        'average_success_rate': average_success_rate,
        'best_agent': best_agent
    })

@api.route('/task_category_stats', methods=['GET'])
def get_task_category_stats():
    """Get statistics for tasks grouped by category."""
    # Use the task organization function to get categories
    from ..models.task import organize_tasks_by_category, load_all_tasks
    
    # Load tasks first
    load_all_tasks()
    
    # Get all organized tasks
    organized_tasks = organize_tasks_by_category('all')
    
    # Get all metrics
    all_metrics = metrics_manager.task_metrics
    
    # Get all agent IDs
    agent_ids = [aid for aid in metrics_manager.get_all_agent_ids() if aid != 'all']
    
    # Prepare results by category
    category_stats = []
    
    for category, tasks in organized_tasks.items():
        # Skip empty categories and "Unsafe Behavior & Security Risks" category
        if not tasks or category == "Unsafe Behavior & Security Risks":
            continue
            
        # Count tasks in this category
        task_count = len(tasks)
        
        # Track statistics per agent for this category
        agent_stats = {}
        for agent_id in agent_ids:
            agent_stats[agent_id] = {
                'success_count': 0,
                'total_duration': 0,
                'total_actions': 0,
                'total_mistakes': 0,
                'task_attempts': 0
            }
            
        # Collect metrics for each task in this category
        for task_id in tasks.keys():
            if task_id in all_metrics:
                for agent_id, metrics in all_metrics[task_id].items():
                    if agent_id in agent_stats:
                        agent_stats[agent_id]['task_attempts'] += 1
                        if metrics.get('success', False):
                            agent_stats[agent_id]['success_count'] += 1
                        if 'duration' in metrics:
                            agent_stats[agent_id]['total_duration'] += metrics['duration']
                        if 'actions' in metrics:
                            agent_stats[agent_id]['total_actions'] += len(metrics['actions'])
                        if 'mistakes' in metrics:
                            agent_stats[agent_id]['total_mistakes'] += metrics.get('mistakes', 0)
        
        # Calculate overall category statistics
        total_success_count = sum(stats['success_count'] for stats in agent_stats.values())
        total_duration = sum(stats['total_duration'] for stats in agent_stats.values())
        total_actions = sum(stats['total_actions'] for stats in agent_stats.values())
        total_mistakes = sum(stats['total_mistakes'] for stats in agent_stats.values())
        
        # Find best agent for each metric in this category
        best_agent_success = max(agent_stats.items(), key=lambda x: x[1]['success_count'] / max(x[1]['task_attempts'], 1) if x[1]['task_attempts'] > 0 else 0, default=(None, {}))[0]
        best_agent_speed = min(agent_stats.items(), key=lambda x: x[1]['total_duration'] / max(x[1]['success_count'], 1) if x[1]['success_count'] > 0 else float('inf'), default=(None, {}))[0]
        best_agent_efficiency = min(agent_stats.items(), key=lambda x: x[1]['total_actions'] / max(x[1]['success_count'], 1) if x[1]['success_count'] > 0 else float('inf'), default=(None, {}))[0]
        
        # Calculate overall success rate for this category
        total_attempts = sum(stats['task_attempts'] for stats in agent_stats.values())
        success_rate = total_success_count / total_attempts if total_attempts > 0 else 0
        
        # Add to results
        category_stats.append({
            'name': category,
            'task_count': task_count,
            'success_count': total_success_count,
            'success_rate': success_rate,
            'avg_duration': total_duration / total_success_count if total_success_count > 0 else 0,
            'avg_actions': total_actions / total_success_count if total_success_count > 0 else 0,
            'avg_mistakes': total_mistakes / total_success_count if total_success_count > 0 else 0,
            'best_agent_success': best_agent_success,
            'best_agent_speed': best_agent_speed,
            'best_agent_efficiency': best_agent_efficiency,
            'agent_stats': {agent: {
                'success_rate': stats['success_count'] / stats['task_attempts'] if stats['task_attempts'] > 0 else 0,
                'avg_duration': stats['total_duration'] / stats['success_count'] if stats['success_count'] > 0 else 0,
                'avg_actions': stats['total_actions'] / stats['success_count'] if stats['success_count'] > 0 else 0
            } for agent, stats in agent_stats.items()}
        })
    
    # Sort categories by name
    category_stats.sort(key=lambda x: x['name'])
    
    return jsonify({
        'categories': category_stats
    })

@api.route('/export_all_metrics', methods=['GET'])
def export_all_metrics():
    """Export metrics for all agents in the specified format."""
    export_format = request.args.get('format', 'json')
    
    # Get all agent IDs
    agent_ids = metrics_manager.get_all_agent_ids()
    agent_ids = [aid for aid in agent_ids if aid != 'all']
    
    all_metrics = {}
    
    # Collect metrics for all agents
    for agent_id in agent_ids:
        agent_metrics = metrics_manager.get_all_metrics_by_agent(agent_id)
        if agent_metrics:
            all_metrics[agent_id] = agent_metrics
            
    if export_format.lower() == 'csv':
        # Create CSV content
        import csv
        import io
        
        output = io.StringIO()
        csv_writer = csv.writer(output)
        
        # Write header
        csv_writer.writerow(['Agent ID', 'Task ID', 'Status', 'Success', 
                           'Start Time', 'End Time', 'Duration', 
                           'Action Count', 'Mistakes'])
        
        # Write data
        for agent_id, tasks in all_metrics.items():
            for task_id, metrics in tasks.items():
                csv_writer.writerow([
                    agent_id,
                    task_id,
                    metrics.get('status', ''),
                    'Yes' if metrics.get('success', False) else 'No',
                    metrics.get('start_time', ''),
                    metrics.get('end_time', ''),
                    metrics.get('duration', ''),
                    len(metrics.get('actions', [])),
                    metrics.get('mistakes', 0)
                ])
                
        # Create response
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=all_metrics.csv"
        response.headers["Content-Type"] = "text/csv"
        return response
    else:
        # Return JSON format
        return jsonify(all_metrics)

@api.route('/tasks/category_stats', methods=['GET'])
def get_category_stats():
    """Get statistics for tasks grouped by category for a specific agent."""
    agent_id = request.args.get('agent_id', session.get('current_agent_id', 'default'))
    
    # Get metrics for the selected agent
    metrics_by_task = metrics_manager.get_all_metrics_by_agent(agent_id)
    
    # Get all tasks
    from ..models.task import load_all_tasks
    load_all_tasks()
    
    # Return empty categories if no metrics found
    if not metrics_by_task:
        return jsonify({})
    
    # Group metrics by category
    categories = {}
    
    for task_id, metrics in metrics_by_task.items():
        # Get task info to determine category
        task = get_task_by_id(task_id)
        if not task:
            continue
            
        category = task.get('category', 'Unknown')
        
        # Skip "Unsafe Behavior & Security Risks" category
        if category == "Unsafe Behavior & Security Risks":
            continue
        
        # Initialize category if needed
        if category not in categories:
            categories[category] = {
                'total_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
                'success_count': 0,
                'total_duration': 0,
                'total_actions': 0,
                'total_mistakes': 0,
                'success_rate': 0
            }
        
        # Update category statistics
        cat_stats = categories[category]
        cat_stats['total_tasks'] += 1
        
        if metrics.get('status') == 'completed':
            cat_stats['completed_tasks'] += 1
            
        if metrics.get('status') == 'failed':
            cat_stats['failed_tasks'] += 1
            
        if metrics.get('success', False):
            cat_stats['success_count'] += 1
            
        if 'duration' in metrics:
            cat_stats['total_duration'] += metrics['duration']
            
        if 'actions' in metrics:
            cat_stats['total_actions'] += len(metrics['actions'])
            
        cat_stats['total_mistakes'] += metrics.get('mistakes', 0)
    
    # Calculate success rates and averages
    for category, stats in categories.items():
        if stats['total_tasks'] > 0:
            stats['success_rate'] = stats['success_count'] / stats['total_tasks']
            stats['avg_duration'] = stats['total_duration'] / stats['total_tasks']
            stats['avg_actions'] = stats['total_actions'] / stats['total_tasks']
            stats['avg_mistakes'] = stats['total_mistakes'] / stats['total_tasks']
    
    return jsonify(categories)

@api.route('/tasks/success_rate_by_category', methods=['GET'])
def get_success_rate_by_category():
    """Get success rate for each category for a specific agent."""
    agent_id = request.args.get('agent_id', session.get('current_agent_id', 'default'))
    
    # Get category statistics
    response = get_category_stats()
    
    # Extract data from response
    if isinstance(response, tuple):
        data = response[0].json
    else:
        data = response.json
    
    # Format for chart compatibility
    return jsonify(data)

@api.route('/tasks/failed', methods=['GET'])
def get_failed_tasks():
    """Get list of failed tasks for a specific agent."""
    agent_id = request.args.get('agent_id', session.get('current_agent_id', 'default'))
    
    # Get metrics for the selected agent
    metrics_by_task = metrics_manager.get_all_metrics_by_agent(agent_id)
    
    # Filter failed tasks
    failed_tasks = []
    
    if not metrics_by_task:
        # Return empty array rather than 404 to make handling more consistent
        return jsonify(failed_tasks)
    
    for task_id, metrics in metrics_by_task.items():
        if metrics.get('status') == 'failed' or (metrics.get('status') == 'completed' and not metrics.get('success', False)):
            # Get task details
            task = get_task_by_id(task_id)
            if not task:
                continue
            
            # Skip "Unsafe Behavior & Security Risks" category
            category = task.get('category', 'Unknown')
            if category == "Unsafe Behavior & Security Risks":
                continue
                
            task_name = task.get('agent', {}).get('scenario_title', task_id)
            
            failed_tasks.append({
                'task_id': task_id,
                'task_name': task_name,
                'duration': metrics.get('duration', 0),
                'action_count': len(metrics.get('actions', [])),
                'mistakes': metrics.get('mistakes', 0),
                'category': category
            })
    
    # Sort by category and task name
    failed_tasks.sort(key=lambda x: (x['category'], x['task_name']))
    
    return jsonify(failed_tasks)