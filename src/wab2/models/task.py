from typing import Dict, List, Optional
from dataclasses import dataclass
import json
import os
import glob
from . import task_state_manager
from . import global_settings

# Simple console log function
def console_log(message):
    print(f"[TaskModel] {message}")

@dataclass
class Task:
    """Task data model."""
    id: str
    category: str
    status: str = "pending"
    template: str = ""
    route: str = ""
    agent: Dict = None
    observer: Dict = None
    settings: Dict = None

# Tasks will be loaded from JSON files
tasks: List[Dict] = []

def load_all_tasks(agent_id='default'):
    """Load tasks from all JSON files in the tasks directory."""
    global tasks
    tasks = []

    console_log(f"Loading all tasks for agent {agent_id}")
    
    # Get the directory where task JSON files are stored
    tasks_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'tasks')
    
    # If the directory doesn't exist yet, create it
    if not os.path.exists(tasks_dir):
        os.makedirs(tasks_dir)
        return tasks
    
    # Find all JSON files in the tasks directory
    task_files = glob.glob(os.path.join(tasks_dir, "*.json"))
    
    for file_path in task_files:
        try:
            with open(file_path, 'r') as f:
                file_tasks = json.load(f)
                # Check if it's a list of tasks or a single task
                if isinstance(file_tasks, list):
                    tasks.extend(file_tasks)
                else:
                    tasks.append(file_tasks)

        except (json.JSONDecodeError, IOError) as e:
            console_log(f"Error loading tasks from {file_path}: {e}")
    
    # Apply state to loaded tasks for the specific agent
    tasks = task_state_manager.apply_states_to_tasks(tasks, agent_id)
    
    return tasks

def save_tasks_to_file(category: str):
    """Save tasks of a specific category to their JSON file."""
    tasks_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'tasks')
    
    # If the directory doesn't exist yet, create it
    if not os.path.exists(tasks_dir):
        os.makedirs(tasks_dir)
    
    # Get tasks for the category
    category_tasks = [task for task in tasks if task['category'] == category]
    
    # Create clean task definitions (without status) for saving
    clean_tasks = []
    for task in category_tasks:
        # Create a copy of the task without the status field
        clean_task = {k: v for k, v in task.items() if k != 'status'}
        clean_tasks.append(clean_task)
    
    # Create a safe filename from the category
    # First, replace special characters with underscores
    safe_category = ''.join(c if c.isalnum() or c == ' ' else '_' for c in category)
    # Then replace spaces with underscores and convert to lowercase
    safe_category = safe_category.lower().replace(' ', '_')
    # Remove any duplicate underscores
    safe_category = '_'.join(filter(None, safe_category.split('_')))
    
    # Save to file
    file_path = os.path.join(tasks_dir, f"{safe_category}.json")
    console_log(f"Saving {len(clean_tasks)} tasks to {file_path}")
    with open(file_path, 'w') as f:
        json.dump(clean_tasks, f, indent=2)

def get_task_by_id(task_id: str) -> Optional[Dict]:
    """Get a task by its ID."""
    return next((task for task in tasks if task['id'] == task_id), None)

def update_task_status(task_id: str, new_status: str = "completed", agent_id: str = 'default') -> bool:
    """Update the status of a task for a specific agent."""
    task = get_task_by_id(task_id)
    if task:
        # Update in-memory task
        task['status'] = new_status
        
        # Update state manager with agent-specific state
        task_state_manager.update_task_state(task_id, new_status, agent_id)
        
        return True
    return False

def add_task(task_data: Dict, agent_id: str = 'default') -> bool:
    """Add a new task to the collection."""
    # Add an ID if not provided
    if 'id' not in task_data:
        # Generate a simple ID from the scenario title if available
        if task_data.get('agent') and task_data['agent'].get('scenario_title'):
            # Create slug from title
            simple_id = task_data['agent']['scenario_title'].lower()
            simple_id = simple_id.replace(' ', '_')
            # Remove non-alphanumeric characters
            simple_id = ''.join(c for c in simple_id if c.isalnum() or c == '_')
        else:
            simple_id = f"task_{len(tasks) + 1}"
        
        task_data['id'] = simple_id
    
    # Get status if provided, default to "pending"    
    status = task_data.get('status', 'pending')
    
    # Add to in-memory collection (with status for this session)
    tasks.append(task_data)
    
    # Save to file (which will strip status)
    save_tasks_to_file(task_data['category'])
    
    # Update state manager with the status for this agent
    task_state_manager.update_task_state(task_data['id'], status, agent_id)
    
    return True

def organize_tasks_by_category(agent_id='default') -> Dict[str, Dict[str, Dict]]:
    """Organize tasks by category and prepare them for the template."""

    # Load tasks with states for the specific agent
    load_all_tasks(agent_id)
    
    organized = {}
    for task in tasks:
        # Skip tasks with missing required fields
        if not task.get('id'):
            console_log(f"WARNING: Task is missing ID")
            continue
            
        if not task.get('category'):
            console_log(f"WARNING: Task {task.get('id')} is missing category")
            continue
            
        if not task.get('agent'):
            console_log(f"WARNING: Task {task['id']} is missing agent data")
            continue
            
        if not task['agent'].get('scenario_title'):
            console_log(f"WARNING: Task {task['id']} is missing scenario_title")
            continue
        
        category = task['category']
        if category not in organized:
            organized[category] = {}
        
        # ALWAYS use task ID for the URL
        task_url = f"/tasks/{task['id']}"
        
        # For security tasks, don't show status and add a disclaimer
        is_security_task = (category == "Unsafe Behavior & Security Risks")
        
        task_entry = {
            'observer_title': task['agent'].get('scenario_title', "Unknown Task"),
            'url': task_url,
            'observer_notes': _generate_observer_notes(task)
        }
        
        # Only add status for non-security tasks
        if is_security_task:
            task_entry['status'] = "not_tracked"
        else:
            task_entry['status'] = task['status']
        
        organized[category][task['id']] = task_entry
        
        # Include global settings info rather than task-specific settings
        time_limit = global_settings.get_time_limit()
        max_attempts = global_settings.get_max_attempts()
        organized[category][task['id']]['settings_info'] = f"Time limit: {time_limit}s, Max attempts: {max_attempts}"
    
    # Define custom category order
    category_order = [
        "Action Capabilities",
        "Dynamic UI & State Awareness",
        "Ambiguity & Semantic Traps",
        "Unsafe Behavior & Security Risks"
    ]
    
    # Create OrderedDict with custom order
    from collections import OrderedDict
    ordered_result = OrderedDict()
    
    # First add categories in specified order
    for category in category_order:
        if category in organized:
            ordered_result[category] = organized[category]
    
    # Then add any other categories that might not be in the custom order list
    for category in organized:
        if category not in ordered_result:
            ordered_result[category] = organized[category]
    
    return ordered_result

def _generate_observer_notes(task: Dict) -> str:
    """Generate HTML for observer notes from task data."""
    if not task.get('observer'):
        return "<p>No observer notes available.</p>"
        
    def escape_html(text):
        if isinstance(text, str):
            return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return str(text)
        
    observer = task['observer']
    notes = "<h4>Goal</h4>"
    notes += f"<p>{escape_html(observer.get('goal', 'N/A'))}</p>"
    
    if observer.get('scenario_summary'):
        notes += "<h4>Scenario</h4>"
        if isinstance(observer['scenario_summary'], list):
            notes += "<ul>"
            for item in observer['scenario_summary']:
                notes += f"<li>{escape_html(item)}</li>"
            notes += "</ul>"
        else:
            notes += f"<p>{escape_html(observer['scenario_summary'])}</p>"
    
    if observer.get('key_observations'):
        notes += "<h4>Key Observations</h4><ul>"
        for obs in observer['key_observations']:
            notes += f"<li>{escape_html(obs)}</li>"
        notes += "</ul>"
    
    if observer.get('success_criteria'):
        notes += "<h4>Success Criteria</h4>"
        if isinstance(observer['success_criteria'], list):
            notes += "<ul>"
            for item in observer['success_criteria']:
                notes += f"<li>{escape_html(item)}</li>"
            notes += "</ul>"
        else:
            notes += f"<p>{escape_html(observer['success_criteria'])}</p>"
    
    return notes