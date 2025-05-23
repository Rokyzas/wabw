import json
import os
from typing import Dict, List
import datetime

# Simple console log function
def console_log(message):
    print(f"[TaskStateManager] {message}")

# Path to store task states
STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'state', 'task_states.json')

# Task states in memory - organized by task_id and agent_id
# Structure: {task_id: {agent_id: state_data}}
task_states = {}

def initialize():
    """Initialize the task state manager."""
    # Create state directory if it doesn't exist
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    
    # Load existing states or create empty state file
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                global task_states
                loaded_states = json.load(f)
                
                task_states = loaded_states
                
                # Count total states
                total_states = sum(len(agents) for agents in task_states.values())
                console_log(f"Loaded states for {len(task_states)} tasks across {total_states} agent combinations")
        except (json.JSONDecodeError, IOError) as e:
            console_log(f"Error loading task states: {e}")
            task_states = {}
            save_states()
    else:
        console_log("No task states file found, creating new one")
        save_states()

def migrate_task_states(old_states):
    """Migrate task states from old format to new agent-specific format."""
    new_states = {}
    
    for task_id, state in old_states.items():
        new_states[task_id] = {
            # Store the old state under the 'default' agent
            'default': state
        }
    
    return new_states

def get_task_state(task_id, agent_id='default'):
    """Get the current state for a task and agent."""
    # Get all states for this task
    task_states_for_id = task_states.get(task_id, {})
    
    # Get state for this specific agent
    return task_states_for_id.get(agent_id, {"status": "pending"})

def update_task_state(task_id, status, agent_id='default', **kwargs):
    """Update a task's state for a specific agent."""
    # Initialize task entry if it doesn't exist
    if task_id not in task_states:
        task_states[task_id] = {}
    
    # Initialize agent entry if it doesn't exist
    if agent_id not in task_states[task_id]:
        task_states[task_id][agent_id] = {}
        
    # Update status
    task_states[task_id][agent_id]["status"] = status
    task_states[task_id][agent_id]["last_updated"] = datetime.datetime.now().isoformat()
    
    # Update any additional state fields
    for key, value in kwargs.items():
        task_states[task_id][agent_id][key] = value
    
    # Save to file
    save_states()
    
    return task_states[task_id][agent_id]

def reset_task_state(task_id, agent_id=None):
    """Reset state for a specific task and agent.
    
    If agent_id is provided, only reset state for that agent.
    Otherwise, reset state for all agents on this task.
    """
    if task_id in task_states:
        if agent_id:
            # Only reset for specific agent
            if agent_id in task_states[task_id]:
                del task_states[task_id][agent_id]
                
                # If no more agents for this task, remove the task
                if not task_states[task_id]:
                    del task_states[task_id]
                    
                console_log(f"Reset state for task {task_id} and agent {agent_id}")
                save_states()
                return True
        else:
            # Reset all agents for this task
            del task_states[task_id]
            console_log(f"Reset state for task {task_id} (all agents)")
            save_states()
            return True
    
    return False

def reset_all_task_states(agent_id=None):
    """Reset all task states to pending.
    
    If agent_id is provided, only reset states for that agent.
    Otherwise, reset all states for all agents.
    """
    global task_states
    
    if agent_id:
        # Remove only states for the specified agent
        for task_id in list(task_states.keys()):
            if agent_id in task_states[task_id]:
                del task_states[task_id][agent_id]
                # If task has no more agents, remove it
                if not task_states[task_id]:
                    del task_states[task_id]
        console_log(f"All task states reset for agent {agent_id}")
    else:
        # Reset all states
        task_states = {}
        console_log("All task states reset")
    
    # Save to file
    save_states()

def save_states():
    """Save all task states to file."""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(task_states, f, indent=2)
    except IOError as e:
        console_log(f"Error saving task states: {e}")

def apply_states_to_tasks(tasks, agent_id='default'):
    """Apply stored states to task definitions for a specific agent."""
    for task in tasks:
        if 'id' in task:
            # Apply state for this agent if exists, otherwise use default state
            state = get_task_state(task['id'], agent_id)
            task['status'] = state.get('status', task.get('status', 'pending'))
    
    return tasks

def get_all_agent_ids():
    """Get all unique agent IDs from task states."""
    agent_ids = set()
    
    # Add the default agent ID
    agent_ids.add('default')
    
    # Check all task states for agent IDs
    for agents in task_states.values():
        agent_ids.update(agents.keys())
    
    return list(agent_ids)