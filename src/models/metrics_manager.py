import json
import os
from typing import Dict, List, Any
import datetime
from datetime import datetime

# Simple console log function
def console_log(message):
    print(f"[MetricsManager] {message}")

# Path to store metrics data
METRICS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'state', 'metrics.json')

# Metrics in memory - organized by task_id and agent_id
# Structure: {task_id: {agent_id: metrics_data}}
task_metrics = {}

def initialize():
    """Initialize the metrics manager."""
    # Create state directory if it doesn't exist
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    
    # Load existing metrics or create empty metrics file
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, 'r') as f:
                global task_metrics
                task_metrics = json.load(f)
                
                # Count total metrics
                total_metrics = sum(len(agents) for agents in task_metrics.values())
                console_log(f"Loaded metrics for {len(task_metrics)} tasks and {total_metrics} total task-agent combinations")
        except (json.JSONDecodeError, IOError) as e:
            console_log(f"Error loading metrics: {e}")
            task_metrics = {}
            save_metrics()
    else:
        console_log("No metrics file found, creating new one")
        save_metrics()

def get_task_metrics(task_id):
    """Get all metrics for a specific task, across all agents."""
    return task_metrics.get(task_id, {})

def get_task_metrics_for_agent(task_id, agent_id):
    """Get metrics for a specific task and agent."""
    task_data = task_metrics.get(task_id, {})
    return task_data.get(agent_id, {})

def update_task_metrics(task_id, agent_id=None, status=None, success=None, **kwargs):
    """Update a task's metrics for a specific agent."""
    if not agent_id:
        agent_id = 'default'
        
    # Initialize task entry if it doesn't exist
    if task_id not in task_metrics:
        task_metrics[task_id] = {}
        
    # Initialize agent entry if it doesn't exist
    if agent_id not in task_metrics[task_id]:
        task_metrics[task_id][agent_id] = {
            'start_time': datetime.now().isoformat(),
            'actions': [],
            'mistakes': 0,
            'status': 'in_progress',
            'agent_id': agent_id
        }
    
    # Update specific fields if provided
    if status:
        task_metrics[task_id][agent_id]['status'] = status
    
    if success is not None:
        task_metrics[task_id][agent_id]['success'] = success
    
    # Update any additional fields
    for key, value in kwargs.items():
        task_metrics[task_id][agent_id][key] = value
    
    # Add a last_updated timestamp
    task_metrics[task_id][agent_id]["last_updated"] = datetime.now().isoformat()
    
    # Save to file
    save_metrics()
    
    return task_metrics[task_id][agent_id]

def log_action(task_id, action, element='', value='', agent_id=None):
    """Log an action for a task."""
    if not agent_id:
        agent_id = 'default'
        
    # Initialize metrics if not exists
    if task_id not in task_metrics:
        task_metrics[task_id] = {}
        
    if agent_id not in task_metrics[task_id]:
        task_metrics[task_id][agent_id] = {
            'start_time': datetime.now().isoformat(),
            'actions': [],
            'mistakes': 0,
            'status': 'in_progress',
            'agent_id': agent_id
        }
    
    # Log the action
    task_metrics[task_id][agent_id]['actions'].append({
        'timestamp': datetime.now().isoformat(),
        'action': action,
        'element': element,
        'value': value,
        'agent_id': agent_id
    })
    
    # Save to file
    save_metrics()
    
    return len(task_metrics[task_id][agent_id]['actions'])

def record_mistake(task_id, mistake_type='unspecified', details='', agent_id=None):
    """Record a mistake for a task."""
    if not agent_id:
        agent_id = 'default'
        
    # Initialize metrics if not exists
    if task_id not in task_metrics:
        task_metrics[task_id] = {}
        
    if agent_id not in task_metrics[task_id]:
        task_metrics[task_id][agent_id] = {
            'start_time': datetime.now().isoformat(),
            'actions': [],
            'mistakes': 0,
            'status': 'in_progress',
            'agent_id': agent_id
        }
    
    # Increment mistakes counter
    task_metrics[task_id][agent_id]['mistakes'] += 1
    
    # Log the mistake
    if 'mistake_log' not in task_metrics[task_id][agent_id]:
        task_metrics[task_id][agent_id]['mistake_log'] = []
    
    task_metrics[task_id][agent_id]['mistake_log'].append({
        'timestamp': datetime.now().isoformat(),
        'type': mistake_type,
        'details': details,
        'agent_id': agent_id
    })
    
    # Save to file
    save_metrics()
    
    return task_metrics[task_id][agent_id]['mistakes']

def complete_task(task_id, success=False, notes='', agent_id=None):
    """Mark a task as completed and calculate final metrics."""
    if not agent_id:
        agent_id = 'default'
        
    # Initialize metrics if not exists
    if task_id not in task_metrics:
        task_metrics[task_id] = {}
        
    if agent_id not in task_metrics[task_id]:
        task_metrics[task_id][agent_id] = {
            'start_time': datetime.now().isoformat(),
            'actions': [],
            'mistakes': 0,
            'agent_id': agent_id
        }
    
    # Calculate duration if not already completed
    if 'end_time' not in task_metrics[task_id][agent_id]:
        end_time = datetime.now()
        
        # Convert start_time to datetime if it's a string
        start_time = task_metrics[task_id][agent_id].get('start_time')
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time)
            except ValueError:
                # Default to now if we can't parse the timestamp
                start_time = end_time
        elif not start_time:
            start_time = end_time
            
        # Calculate duration in seconds
        if isinstance(start_time, datetime):
            duration = (end_time - start_time).total_seconds()
        else:
            duration = 0
        
        # Update task metrics
        task_metrics[task_id][agent_id].update({
            'end_time': end_time.isoformat(),
            'duration': duration,
            'success': success,
            'notes': notes,
            'status': 'completed' if success else 'failed'
        })
    
    # Save to file
    save_metrics()
    
    return task_metrics[task_id][agent_id]

def reset_task_metrics(task_id, agent_id=None):
    """Reset metrics for a specific task and agent.
    
    If agent_id is provided, only reset metrics for that agent.
    Otherwise, reset metrics for all agents on this task.
    """
    global task_metrics
    
    if task_id in task_metrics:
        if agent_id:
            # Only reset for the specific agent
            if agent_id in task_metrics[task_id]:
                del task_metrics[task_id][agent_id]
                console_log(f"Metrics reset for task {task_id} and agent {agent_id}")
                
                # If no more agents for this task, remove the task entry
                if not task_metrics[task_id]:
                    del task_metrics[task_id]
                
                save_metrics()
                return True
        else:
            # Reset for all agents on this task
            del task_metrics[task_id]
            console_log(f"Metrics reset for task {task_id} (all agents)")
            save_metrics()
            return True
    
    return False

def reset_all_metrics(agent_id=None):
    """Reset metrics for a specific agent or all metrics if agent_id is None."""
    global task_metrics
    
    if agent_id:
        # Remove only metrics for the specified agent
        for task_id in list(task_metrics.keys()):
            if agent_id in task_metrics[task_id]:
                del task_metrics[task_id][agent_id]
                # If task has no more agents, remove it
                if not task_metrics[task_id]:
                    del task_metrics[task_id]
        console_log(f"Metrics reset for agent {agent_id}")
    else:
        # Reset all metrics
        task_metrics = {}
        console_log("All metrics reset")
    
    # Save to file
    save_metrics()

def save_metrics():
    """Save all metrics to file."""
    try:
        with open(METRICS_FILE, 'w') as f:
            json.dump(task_metrics, f, indent=2)
    except IOError as e:
        console_log(f"Error saving metrics: {e}")

def get_all_metrics():
    """Get all task metrics in a flattened structure for backwards compatibility."""
    flattened_metrics = {}
    
    for task_id, agents in task_metrics.items():
        for agent_id, metrics in agents.items():
            # Use task_id as key, but add a suffix for multiple agents
            key = f"{task_id}_{agent_id}" if agent_id != 'default' else task_id
            flattened_metrics[key] = metrics
    
    return flattened_metrics

def get_all_metrics_by_agent(agent_id=None):
    """Get all metrics for a specific agent, or all agents if agent_id is None."""
    results = {}
    
    for task_id, agents in task_metrics.items():
        if agent_id:
            # Filter for specific agent
            if agent_id in agents:
                results[task_id] = agents[agent_id]
        else:
            # Include all agents
            results[task_id] = agents
            
    return results

def get_all_agent_ids():
    """Get all unique agent IDs from metrics."""
    agent_ids = set()
    
    # Add the default agent ID
    agent_ids.add('default')
    
    # Check all task metrics for agent IDs
    for agents in task_metrics.values():
        agent_ids.update(agents.keys())
    
    return list(agent_ids)

def export_metrics_to_file(agent_id='default'):
    """Export metrics for a specific agent to a JSON file."""
    # Create exports directory if it doesn't exist
    exports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'exports')
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
    
    # Create a timestamp for the filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"metrics_{agent_id}_{timestamp}.json"
    filepath = os.path.join(exports_dir, filename)
    
    # Prepare the export data with additional context
    export_data = {
        'agent_id': agent_id,
        'export_time': datetime.now().isoformat(),
        'task_count': 0,
        'tasks': {}
    }
    
    # Add metrics for this agent
    task_count = 0
    for task_id, agents in task_metrics.items():
        # Skip tasks where this agent doesn't have metrics
        if agent_id != 'all' and agent_id not in agents:
            continue
            
        # For 'all', include all agents' metrics; otherwise, just the specific agent
        if agent_id == 'all':
            export_data['tasks'][task_id] = agents
            task_count += len(agents)
        else:
            export_data['tasks'][task_id] = agents[agent_id]
            task_count += 1
    
    export_data['task_count'] = task_count
    
    # Save to file if there are tasks to export
    if task_count > 0:
        try:
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            return {
                'success': True,
                'message': f'Metrics exported successfully for agent {agent_id}',
                'filename': filename,
                'filepath': filepath,
                'task_count': task_count
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    else:
        return {
            'success': False,
            'message': f'No metrics found for agent {agent_id}'
        } 