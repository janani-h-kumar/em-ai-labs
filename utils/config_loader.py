"""
Enterprise configuration manager — single authoritative copy.

IMPORTANT: Delete utils/config_loader.py (root-level) and update
base_agent.py's import to point here: from src.utils.config_loader import ConfigManager

Changes from original:
- Removed duplicate `import os` at top
- Fixed APP_ENV crash: os.getenv('APP_ENV') returned None without a default,
  causing AttributeError on .lower(). Now defaults to 'dev' safely.
- Removed dead TODO comment block (old env loading code)
- Both src/ and root copies had diverged — this is the canonical version
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from dotenv import dotenv_values, load_dotenv

load_dotenv()

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
    - YAML keys: access normally (e.g., 'runtime.orchestration')
    - .env keys: access via 'env' group (e.g., 'env.OLLAMA_BASE_URL')
    """
    config_path: str
    _config: Dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads YAML first, then captures environment variables into 'env' key."""
        config_file = Path(self.config_path)
        config: Dict[str, Any] = {}

        # 1. Load YAML
        if config_file.exists() and config_file.is_file():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                logger.info(f"Loaded YAML from {self.config_path}")
            except yaml.YAMLError as e:
                raise ConfigError(f"Failed to parse YAML: {e}")
            except Exception as e:
                raise ConfigError(f"Failed to load config file: {e}")
        else:
            logger.warning(f"Config file {self.config_path} not found. Using ENV only.")

        # 2. Locate base .env and determine environment
        env_file_path = config_file.parent.parent / '.env'
        config["env"] = {}

        if env_file_path.exists():
            base_env = dotenv_values(dotenv_path=env_file_path)

            # FIX: was os.getenv('APP_ENV').lower() — crashes with AttributeError if unset.
            # Now uses base_env first, then os.getenv, then safe default 'dev'.
            raw_app_env = (
                base_env.get("APP_ENV")
                or os.getenv("APP_ENV")
                or "dev"
            ).lower()
            suffix = "dev" if raw_app_env == "development" else raw_app_env

            env_specific_path = config_file.parent.parent / f'.env.{suffix}'

            if env_specific_path.exists():
                logger.info(f"Loading environment-specific keys from {env_specific_path.name}")
                config["env"] = dotenv_values(dotenv_path=env_specific_path)
                load_dotenv(env_specific_path, override=True)
            else:
                logger.warning(
                    f"Environment-specific file .env.{suffix} not found. "
                    "Falling back to base .env"
                )
                config["env"] = base_env

        logger.info("Configuration loaded successfully")
        return config

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Get configuration value using dot notation (e.g., 'env.OLLAMA_BASE_URL')"""
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else:
                    return default
            return value
        except (KeyError, TypeError):
            return default

    def get_required(self, key: str) -> Any:
        """Get required value or raise ConfigValidationError with a helpful hint."""
        value = self.get(key)
        if value is None:
            hints = {
                "env.OPENWEATHER_API_KEY": "Add OPENWEATHER_API_KEY to your .env file.",
                "env.OLLAMA_BASE_URL": "Add OLLAMA_BASE_URL to your .env file.",
                "env.OLLAMA_API_KEY": "Add OLLAMA_API_KEY to your .env file.",
            }
            message = f"Missing required config: {key}"
            if key in hints:
                message += f" — Hint: {hints[key]}"
            raise ConfigValidationError(message)
        return value

    def get_all(self) -> Dict[str, Any]:
        """Returns a copy of the full configuration dictionary."""
        return self._config.copy()

    def reload(self) -> None:
        """Reload configuration from disk and environment."""
        self._config = self._load_config()

    def validate_startup(self) -> None:
        """
        Validate all required configuration keys exist at startup.

        Fails fast instead of mid-request crashes.

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
                "Missing required configuration:\n"
                + "\n".join(missing)
                + "\n\nSet these in your .env file and retry."
            )
            logger.error(error_msg)
            raise ConfigValidationError(error_msg)

        logger.info("All required configuration validated")

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value using dot notation (in-memory only)."""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value


# Backward compatibility
def load_config(config_path: str) -> Dict[str, Any]:
    return ConfigManager(config_path).get_all()