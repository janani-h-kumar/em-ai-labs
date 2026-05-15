import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass
from dotenv import dotenv_values, load_dotenv

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
    Enterprise configuration manager with validation and dot notation access

    Features:
    - YAML configuration loading
    - Dot notation access (e.g., 'ollama.host')
    - Configuration validation
    - Environment variable support for sensitive values via .env
    - Comprehensive error handling
    """

    config_path: str

    def __post_init__(self):
        """Load configuration after initialization"""
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file

        Returns:
            dict: Configuration dictionary

        Raises:
            ConfigError: If loading fails
        """

        config_file = Path(self.config_path)
        logger.info(f"Loading configuration from: {self.config_path}")

        config: Dict[str, Any] = {}

        if config_file.exists():
            if not config_file.is_file():
                raise ConfigError(f"Configuration path is not a file: {self.config_path}")

            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                logger.error(f"YAML parsing error: {e}")
                raise ConfigError(f"Invalid YAML in configuration file: {e}")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                raise ConfigError(f"Failed to load configuration: {e}")
        else:
            logger.info(
                f"Configuration file not found: {self.config_path}. Falling back to environment variables."
            )

        # TODO - looks round about.. revisit 
        base_env_path = Path(__file__).resolve().parent.parent / '.env'
        load_dotenv(dotenv_path=base_env_path)
        
        # Determine Environment (The ONLY place where a default is acceptable)
        app_env = os.getenv("APP_ENV").lower()

        # 3. SECRETS: Load the environment-specific file
        env_file = Path(__file__).resolve().parent.parent / f".env.{app_env}"
        
        # We use dotenv_values to get ONLY the keys from the file 
        # avoiding hardcoded prefixes or system "noise" (like PATH)
        if env_file.exists():
            secrets = dotenv_values(env_file)
            config["env"] = {k.lower(): v for k, v in secrets.items()}
            
            # Also load them into os.environ so other libs (like Ollama) can see them
            load_dotenv(env_file, override=True)
        else:
            config["env"] = {}


        # TODO old implementation - needs to be refactored to use the new env loading logic above
        # app_env = (os.getenv('APP_ENV') or os.getenv('APP_ENVIRONMENT') or '').strip().lower()
        # if app_env:
        #     env_candidates = [f'.env.{app_env}']
        #     if app_env in {'dev', 'development'}:
        #         env_candidates.extend(['.env.dev', '.env.development'])
        #     elif app_env in {'prod', 'production'}:
        #         env_candidates.extend(['.env.prod', '.env.production'])

        #     for candidate in env_candidates:
        #         env_path = config_file.parent / candidate
        #         if env_path.exists():
        #             load_dotenv(dotenv_path=env_path, override=False)
        #             logger.info(f"Loaded environment overrides from: {env_path}")
        #             break

        logger.info("Configuration loaded successfully")
        return config


    def _set_in_dict(self, config: Dict[str, Any], keys: List[str], value: Any) -> None:
        """Set a nested configuration value in a dictionary."""
        node = config
        for key in keys[:-1]:
            if key not in node or not isinstance(node[key], dict):
                node[key] = {}
            node = node[key]
        node[keys[-1]] = value

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Get configuration value using dot notation

        Args:
            key: Configuration key (e.g., 'ollama.host')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config

        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else:
                    return default
            return value
        except KeyError:
            return default

    def get_required(self, key: str) -> Any:
        """
        Get required configuration value

        Args:
            key: Configuration key

        Returns:
            Configuration value

        Raises:
            ConfigValidationError: If key not found
        """
        value = self.get(key)
        if value is None:
            hints = {
                "weather.api_key": "Set WEATHER_API_KEY in configs/.env or your environment.",
                "ollama.host": "Set OLLAMA_HOST in configs/.env or your environment.",
                "ollama.api_key": "Set OLLAMA_API_KEY in configs/.env or your environment.",
            }
            message = f"Required configuration key not found: {key}"
            if key in hints:
                message += f" ({hints[key]})"
            raise ConfigValidationError(message)
        return value

    def validate_required_keys(self, required_keys: list) -> None:
        """
        Validate that all required keys are present

        Args:
            required_keys: List of required configuration keys

        Raises:
            ConfigValidationError: If any required key is missing
        """
        missing_keys = []
        for key in required_keys:
            if self.get(key) is None:
                missing_keys.append(key)

        if missing_keys:
            raise ConfigValidationError(f"Missing required configuration keys: {missing_keys}")

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section

        Args:
            section: Section name

        Returns:
            dict: Section configuration
        """
        return self.get(section, {})

    def reload(self) -> None:
        """
        Reload configuration from file

        Raises:
            ConfigError: If reload fails
        """
        logger.info("Reloading configuration...")
        self._config = self._load_config()
        logger.info("Configuration reloaded successfully")

    def get_all(self) -> Dict[str, Any]:
        """
        Get entire configuration

        Returns:
            dict: Complete configuration
        """
        return self._config.copy()

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value (in-memory only)

        Args:
            key: Configuration key
            value: Value to set
        """
        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
        logger.debug(f"Set configuration: {key} = {value}")


# Backward compatibility function
def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration (backward compatibility)

    Args:
        config_path: Path to configuration file

    Returns:
        dict: Configuration dictionary
    """
    manager = ConfigManager(config_path)
    return manager.get_all()