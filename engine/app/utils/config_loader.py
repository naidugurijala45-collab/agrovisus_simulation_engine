"""
Shared configuration loader for both training and simulation scripts.
"""
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """
    Load configuration from a JSON file.
    
    Args:
        config_path: Path to the JSON configuration file
        
    Returns:
        Dictionary containing configuration data
        
    Raises:
        SystemExit: If configuration file cannot be loaded
    """
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        logger.info(f"Configuration loaded successfully from {config_path}")
        return config_data
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in configuration file {config_path}: {e}")
        raise
    except Exception as e:
        logger.critical(f"Error loading config from {config_path}: {e}", exc_info=True)
        raise
