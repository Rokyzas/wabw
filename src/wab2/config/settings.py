import os

class Config:
    """Base configuration."""
    SECRET_KEY = 'dev_key_for_session'  # Simple key for development
    DEBUG = True  # Enable debug mode for development
    TESTING = False

# Single configuration for now
config = Config 