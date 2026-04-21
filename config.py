"""
HunterAI - Configuration Management
Loads and manages all configuration from local JSON files.
"""

import os
import json

# Base directory for all HunterAI data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Sub-directories
PROJECTS_DIR = os.path.join(DATA_DIR, "projects")
HUNTS_DIR = os.path.join(DATA_DIR, "hunts")
CHATS_DIR = os.path.join(DATA_DIR, "chats")
MODELS_DIR = os.path.join(DATA_DIR, "models")
TOOLS_DIR = os.path.join(DATA_DIR, "tools")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
ACTIONS_DIR = os.path.join(DATA_DIR, "actions")
PLANS_DIR = os.path.join(DATA_DIR, "plans")
VULNS_DIR = os.path.join(DATA_DIR, "vulnerabilities")
TERMINAL_LOGS_DIR = os.path.join(DATA_DIR, "terminal_logs")
SCOPE_DIR = os.path.join(DATA_DIR, "scope")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Default configuration
DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False
    },
    "ai": {
        "default_model": None,
        "max_tokens": 4096,
        "temperature": 0.7
    },
    "scope": {
        "mode": "strict",  # strict or advisory
        "require_legal_acknowledgment": True
    },
    "ui": {
        "theme": "dark_lab",
        "default_mode": "intermediate",  # beginner, intermediate, pro
        "default_exec_mode": "feedback"   # autonomous or feedback
    },
    "first_run": True
}


def ensure_directories():
    """Create all required data directories if they don't exist."""
    dirs = [
        DATA_DIR, PROJECTS_DIR, HUNTS_DIR, CHATS_DIR,
        MODELS_DIR, TOOLS_DIR, ASSETS_DIR, REPORTS_DIR,
        ACTIONS_DIR, PLANS_DIR, VULNS_DIR, TERMINAL_LOGS_DIR, SCOPE_DIR
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def load_config():
    """Load configuration from config.json, create with defaults if missing."""
    ensure_directories()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            # Merge with defaults for any missing keys
            merged = _deep_merge(DEFAULT_CONFIG, config)
            return merged
        except (json.JSONDecodeError, IOError):
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save configuration to config.json."""
    ensure_directories()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _deep_merge(defaults, overrides):
    """Deep merge overrides into defaults."""
    result = defaults.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def get_config_value(key_path, default=None):
    """Get a nested config value using dot notation. E.g. 'server.port'"""
    config = load_config()
    keys = key_path.split(".")
    current = config
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            return default
    return current
