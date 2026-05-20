"""
Enterprise configuration manager — minimally hardened production version.

Key improvements:
- FAIL FAST if config file is missing
- Strict YAML error handling
- Clear ConfigError / ConfigValidationError separation
- Safe env loading (.env + optional environment-specific overrides)
- Explicit startup validation (no silent failures)
"""

from logging import config
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import dotenv_values, load_dotenv

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration loading fails (file/YAML issues)."""
    pass


class ConfigValidationError(ConfigError):
    """Raised when required configuration validation fails."""
    pass


@dataclass
class ConfigManager:
    """
    Minimal production-hardened configuration manager.

    - YAML config is primary source
    - .env provides runtime overrides
    - No silent fallback behavior
    """

    config_path: str
    _config: Dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML config and environment variables."""

        config_file = Path(self.config_path)
        config: Dict[str, Any] = {}

        # ----------------------------
        # 1. FAIL FAST if file missing
        # ----------------------------
        if not config_file.exists() or not config_file.is_file():
            raise ConfigError(f"Config file not found: {self.config_path}")

        # ----------------------------
        # 2. Load YAML safely
        # ----------------------------
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            logger.info(f"Loaded YAML from {self.config_path}")
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML format: {e}")
        except Exception as e:
            raise ConfigError(f"Failed to load config file: {e}")

        # ----------------------------
        # 3. ENV loading (.env + override)
        # ----------------------------
        config["env"] = {}

        env_root = config_file.parent.parent

        base_env_file = env_root / ".env"

        app_env = (
            os.getenv("APP_ENV")
            or "dev"
        ).lower()

        env_specific_file = env_root / f".env.{app_env}"

        # 1. Start with base .env (lowest priority)
        base_env = {}
        if base_env_file.exists():
            base_env = dotenv_values(dotenv_path=base_env_file)
            config["env"].update(base_env)

        # 2. Override with env-specific .env.<env>
        if env_specific_file.exists():
            logger.info(f"Loading environment-specific keys from {env_specific_file.name}")
            env_specific = dotenv_values(dotenv_path=env_specific_file)
            config["env"].update(env_specific)

        # 3. FINAL OVERRIDE: OS environment wins always
        config["env"].update(dict(os.environ))

        logger.info("Configuration loaded successfully")
        return config

    # ----------------------------
    # Public API
    # ----------------------------

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Get config using dot notation (e.g., 'env.OLLAMA_BASE_URL')."""
        keys = key.split(".")
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
        """Get required value or raise ConfigValidationError."""
        value = self.get(key)

        if value is None or (isinstance(value, str) and not value.strip()):
            raise ConfigValidationError(f"Missing required config: {key}")

        return value

    def get_all(self) -> Dict[str, Any]:
        """Return full config (copy)."""
        return self._config.copy()

    def reload(self) -> None:
        """Reload configuration from disk."""
        self._config = self._load_config()

    def validate_startup(self) -> None:
        """
        Fail fast validation of required runtime configuration.
        """

        required_keys = [
            "env.OLLAMA_API_KEY",
            "env.OLLAMA_BASE_URL",
            "env.OPENWEATHER_API_KEY",
            "env.OPENWEATHER_BASE_URL",
            "runtime.orchestration",
        ]

        missing = []

        for key in required_keys:
            value = self.get(key)

            if value is None:
                missing.append(key)
            elif isinstance(value, str) and not value.strip():
                missing.append(key)

        if missing:
            raise ConfigValidationError(
                "Missing required configuration:\n"
                + "\n".join(f"  - {k}" for k in missing)
            )

        logger.info("All required configuration validated")

    def set(self, key: str, value: Any) -> None:
        """Set in-memory config value using dot notation."""
        keys = key.split(".")
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value


# ----------------------------
# Backward compatibility
# ----------------------------

def load_config(config_path: str) -> Dict[str, Any]:
    return ConfigManager(config_path).get_all()