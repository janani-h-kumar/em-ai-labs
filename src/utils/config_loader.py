import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from dotenv import load_dotenv
from dotenv import load_dotenv
import os

# 1. Load the file into the environment
load_dotenv() 

# 2. Now os.getenv will actually see it
app_env = os.getenv('APP_ENV', 'development')

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Raised when configuration loading or validation fails"""
    pass

class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails"""
    pass

@dataclass
class ConfigManager:
    """
    Enterprise configuration manager with YAML and a dedicated 'env' group.
    
    Structure:
    - YAML keys: Access normally (e.g., 'chat.max_history')
    - .env keys: Access via 'env' group (e.g., 'env.ollama_base_url')
    """
    config_path: str
    _config: Dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self):
        """Load configuration after initialization"""
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads YAML first, then captures environment variables into 'env' key."""
        config_file = Path(self.config_path)
        config: Dict[str, Any] = {}

        # 1. Load YAML Configuration
        if config_file.exists() and config_file.is_file():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                logger.info(f"Loaded YAML from {self.config_path}")
            except Exception as e:
                raise ConfigError(f"Failed to parse YAML: {e}")
        else:
            logger.warning(f"Config file {self.config_path} not found. Using ENV only.")

        # 2. Load .env as a dictionary (ignores system variables)
        env_file_path = config_file.parent / '.env'
        if env_file_path.exists():
            # dotenv_values returns a dict of only the keys in that specific file
            config["env"] = dotenv_values(stream=env_file_path)

        logger.info("Configuration loaded successfully")
        return config

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Get configuration value using dot notation (e.g., 'env.ollama_api_key')"""
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_required(self, key: str) -> Any:
        """Get required value or raise error with helpful hint"""
        value = self.get(key)
        if value is None:
            # Provide specific hints for the new structure
            hints = {
                "env.weather_api_key": "Add WEATHER_API_KEY to your .env file.",
                "env.ollama_host": "Add OLLAMA_HOST to your .env file.",
                "env.ollama_api_key": "Add OLLAMA_API_KEY to your .env file.",
            }
            message = f"Missing required config: {key}"
            if key in hints:
                message += f" - Hint: {hints[key]}"
            raise ConfigValidationError(message)
        return value

    def get_all(self) -> Dict[str, Any]:
        """Returns a copy of the full configuration dictionary"""
        return self._config.copy()

    def reload(self) -> None:
        """Reload configuration from disk and environment"""
        self._config = self._load_config()

# Backward compatibility function
def load_config(config_path: str) -> Dict[str, Any]:
    manager = ConfigManager(config_path)
    return manager.get_all()