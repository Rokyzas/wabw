import json
import os
import shutil
from flask import current_app
from datetime import datetime

# Default settings
DEFAULT_SETTINGS = {
    "time_limit_sec": 30,
    "max_attempts": 3,
    "last_updated": None
}

# Global settings
global_settings = {}

def initialize():
    """Initialize global settings from file or create with defaults."""
    global global_settings
    
    # Load or create settings
    settings_path = _get_settings_path()
    
    try:
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                global_settings = json.load(f)
                print(f"Global settings loaded from {settings_path}")
        else:
            # Start with defaults
            global_settings = DEFAULT_SETTINGS.copy()
            global_settings["last_updated"] = datetime.now().isoformat()
            
            # Save to create the file
            _save_settings()
            print(f"Default global settings created at {settings_path}")
    except Exception as e:
        print(f"Error initializing global settings: {e}")
        global_settings = DEFAULT_SETTINGS.copy()

def _get_settings_path():
    """Get the path to the global settings file."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    
    # Create data directory if it doesn't exist
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    return os.path.join(data_dir, 'global_settings.json')

def _save_settings():
    """Save current global settings to file."""
    try:
        # First, update the timestamp
        global_settings["last_updated"] = datetime.now().isoformat()
        
        # Save to file
        settings_path = _get_settings_path()
        
        # Create a backup of the existing file
        if os.path.exists(settings_path):
            backup_path = f"{settings_path}.bak"
            shutil.copy2(settings_path, backup_path)
        
        with open(settings_path, 'w') as f:
            json.dump(global_settings, f, indent=2)
            
        return True
    except Exception as e:
        print(f"Error saving global settings: {e}")
        return False

def get_time_limit():
    """Get the global time limit setting."""
    return global_settings.get("time_limit_sec", DEFAULT_SETTINGS["time_limit_sec"])

def get_max_attempts():
    """Get the global max attempts setting."""
    return global_settings.get("max_attempts", DEFAULT_SETTINGS["max_attempts"])

def get_all_settings():
    """Get all global settings."""
    return global_settings.copy()

def update_settings(new_settings):
    """Update global settings with new values."""
    global global_settings
    
    # Only update keys that are already in our settings
    for key in DEFAULT_SETTINGS.keys():
        if key in new_settings and key != "last_updated":
            global_settings[key] = new_settings[key]
    
    # Save updated settings
    return _save_settings() 