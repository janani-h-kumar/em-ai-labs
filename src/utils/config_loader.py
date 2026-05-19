import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from dotenv import dotenv_values, load_dotenv
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
        
        # 1. Locate the base .env file
        env_file_path = config_file.parent.parent / '.env'
        
        # Initialize an empty env dict in case no files exist
        config["env"] = {}

        if env_file_path.exists():
            # Load base env to find out the current environment (e.g., 'development')
            base_env = dotenv_values(dotenv_path=env_file_path)
            
            # Get APP_ENV (default to 'development' if missing, drop case sensitivity)
            app_env = base_env.get("APP_ENV", "development").lower()
            
            # Map 'development' to '.env.dev', 'production' to '.env.prod', etc.
            # If APP_ENV is already 'dev', it'll use '.env.dev'
            suffix = "dev" if app_env == "development" else app_env
            env_specific_path = config_file.parent.parent / f'.env.{suffix}'
            
            if env_specific_path.exists():
                logger.info(f"Loading environment-specific keys from {env_specific_path.name}")
                # Load the sensitive keys from .env.dev / .env.prod
                config["env"] = dotenv_values(dotenv_path=env_specific_path)
            else:
                logger.warning(f"Environment-specific file {env_specific_path.name} not found. Falling back to base .env")
                config["env"] = base_env
                
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

    def validate_startup(self) -> None:
        """
        Validate all required configuration keys exist at startup.
        
        Fails fast instead of mid-request crashes. Checks for essential
        keys needed by the application.
        
        Raises:
            ConfigValidationError: If required configuration is missing
        """
        required_keys = {
            "env.OLLAMA_API_KEY": "Ollama API key (set OLLAMA_API_KEY in .env)",
            "env.OLLAMA_BASE_URL": "Ollama base URL (set OLLAMA_BASE_URL in .env)",
            "env.OPENWEATHER_API_KEY": "OpenWeather API key (set OPENWEATHER_API_KEY in .env)",
            "env.OPENWEATHER_BASE_URL": "OpenWeather base URL (set OPENWEATHER_BASE_URL in .env)",
            "runtime.orchestration": "Runtime type: 'langchain' or 'custom'",
        }
        
        missing = []
        for key, description in required_keys.items():
            value = self.get(key)
            if not value or (isinstance(value, str) and not value.strip()):
                missing.append(f"  {key}: {description}")
        
        if missing:
            error_msg = (
                "❌ Missing required configuration:\n" +
                "\n".join(missing) +
                "\n\nSet these in your .env file and retry."
            )
            logger.error(error_msg)
            raise ConfigValidationError(error_msg)
        
        logger.info("✅ All required configuration validated")

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'runtime.orchestration')
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value

# Backward compatibility function
def load_config(config_path: str) -> Dict[str, Any]:
    manager = ConfigManager(config_path)
    return manager.get_all()