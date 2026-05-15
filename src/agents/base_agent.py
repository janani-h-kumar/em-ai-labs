from abc import ABC, abstractmethod
import logging
from typing import Optional, Dict, Any
from utils.config_loader import ConfigManager


class BaseAgent(ABC):
    """
    Enterprise-ready base agent with proper configuration, logging, and error handling

    This base class provides:
    - Configuration management
    - Logging setup
    - Initialization lifecycle
    - Error handling patterns
    - Health check capabilities
    """

    def __init__(self, config_path: str = "../configs/config.yaml"):
        """
        Initialize base agent with configuration

        Args:
            config_path: Path to the configuration YAML file

        Raises:
            Exception: If initialization fails
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_path = config_path
        self.config_manager = ConfigManager(config_path)
        self._initialized = False

        try:
            self.initialize()
            self._initialized = True
            self.logger.info(f"{self.__class__.__name__} initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize {self.__class__.__name__}: {e}")
            raise

    @abstractmethod
    def initialize(self) -> None:
        """
        Setup API clients, prompts, tools, etc.
        Subclasses must implement this method.
        """
        pass

    @abstractmethod
    def handle(self, message: str) -> str:
        """
        Process user message and return response.
        Subclasses must implement this method.

        Args:
            message: User input message

        Returns:
            str: Agent response
        """
        pass

    def is_initialized(self) -> bool:
        """
        Check if agent is properly initialized

        Returns:
            bool: True if initialized, False otherwise
        """
        return self._initialized

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the agent

        Returns:
            dict: Health status information
        """
        return {
            "agent": self.__class__.__name__,
            "initialized": self._initialized,
            "status": "healthy" if self._initialized else "unhealthy",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }

    def get_config(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Get configuration value using dot notation

        Args:
            key: Configuration key (e.g., 'ollama.base_url')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config_manager.get(key, default)