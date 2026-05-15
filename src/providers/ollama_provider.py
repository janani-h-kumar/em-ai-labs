import logging
from typing import Optional, Union, List, Dict
import requests
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Custom Exceptions
class OllamaError(Exception):
    """Base exception for Ollama-related errors"""
    pass


class ModelNotFoundError(OllamaError):
    """Raised when the specified model is not found locally"""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when unable to connect to Ollama server"""
    pass


class OllamaConfigError(OllamaError):
    """Raised when Ollama configuration is missing or invalid."""
    pass


class OllamaClient:
    """Manages interaction with local Ollama server"""

    def __init__(self, config_manager):
        """
        Initialize OllamaClient with configuration

        Args:
            config_manager: ConfigManager-like instance with loaded configuration

        Raises:
            OllamaConfigError: If Ollama configuration is missing or invalid
            OllamaConnectionError: If unable to connect to Ollama server
            ModelNotFoundError: If specified model is not available locally
        """
        self.config = config_manager
        self.base_url = config_manager.get("ollama.base_url")
        self.api_key = config_manager.get("ollama.api_key")
        self.model = config_manager.get("ollama.model")

        if not self.base_url or not self.api_key:
            raise OllamaConfigError(
                "Ollama base_url and api_key must be configured."
            )

        # Validate connection and model availability
        self._validate_connection()
        self._validate_model_exists()

        # Initialize OpenAI client
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        logger.info(f"OllamaClient initialized with model: {self.model}")

    def _validate_connection(self) -> None:
        """
        Check if Ollama server is running and accessible
        
        Raises:
            OllamaConnectionError: If unable to connect
        """
        try:
            response = requests.get(
                f"{self.base_url.replace('/v1', '')}/api/tags",
                timeout=5
            )
            if response.status_code != 200:
                raise OllamaConnectionError(
                    f"Ollama server returned status {response.status_code}"
                )
            logger.info("Successfully connected to Ollama server")
        except requests.ConnectionError:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama server at {self.base_url}. "
                "Make sure Ollama is running."
            )
        except requests.Timeout:
            raise OllamaConnectionError(
                f"Ollama server at {self.base_url} is not responding (timeout)"
            )

    def _validate_model_exists(self) -> None:
        """
        Check if the specified model is available locally, or auto-select if none specified
        
        Raises:
            ModelNotFoundError: If model not found or no models available
        """
        try:
            # If no model specified, try to auto-select from running models
            if not self.model:
                self.model = self._auto_select_model()
                if not self.model:
                    raise ModelNotFoundError(
                        "No model specified in config and no running models found. "
                        "Either specify a model in config.yaml or start a model with 'ollama run <model-name>'"
                    )
                logger.info(f"Auto-selected running model: {self.model}")
                return

            # Check if specified model is available
            response = requests.get(
                f"{self.base_url.replace('/v1', '')}/api/tags",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            available_models = [m["name"] for m in data.get("models", [])]

            if not available_models:
                raise ModelNotFoundError(
                    "No models available on Ollama server. "
                    "Pull a model first using: ollama pull <model-name>"
                )

            # Check if our model is in the list (handle versioning like "phi3:latest")
            model_found = any(
                self.model in model or model.startswith(self.model)
                for model in available_models
            )

            if not model_found:
                raise ModelNotFoundError(
                    f"Model '{self.model}' not found locally. "
                    f"Available models: {', '.join(available_models)}. "
                    f"Pull it using: ollama pull {self.model}"
                )

            logger.info(f"Model '{self.model}' is available locally")

        except requests.RequestException as e:
            raise OllamaConnectionError(f"Error checking model availability: {e}")

    def _auto_select_model(self) -> Optional[str]:
        """
        Auto-select a model from currently running models
        
        Returns:
            str: Name of the selected model, or None if no running models
        """
        try:
            # Check running models first
            response = requests.get(
                f"{self.base_url.replace('/v1', '')}/api/ps",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            running_models = [m["name"] for m in data.get("models", [])]
            
            if running_models:
                # Return the first running model
                return running_models[0]
            
            # Fall back to available models if none are running
            response = requests.get(
                f"{self.base_url.replace('/v1', '')}/api/tags",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            available_models = [m["name"] for m in data.get("models", [])]
            
            if available_models:
                # Return the first available model
                return available_models[0]
                
        except requests.RequestException:
            pass  # Ignore errors, will return None
            
        return None

    def chat_completion(self, content: Union[str, Dict, List[Dict]]) -> str:
        """
        Send a message to the model and get a response.
        Supports both simple strings and multi-turn conversations.
        
        Args:
            content: Can be one of:
                - str: Simple user message (wrapped as {"role": "user", "content": "..."})
                - dict: Single message with "role" and "content" keys
                - list: List of message dicts for multi-turn conversations
                
        Returns:
            str: The model's response
            
        Raises:
            OllamaError: If the API call fails
            
        Examples:
            # Simple message
            response = ollama.chat_completion("What is AI?")
            
            # Multi-turn conversation
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is AI?"},
                {"role": "assistant", "content": "AI is..."},
                {"role": "user", "content": "Tell me more."}
            ]
            response = ollama.chat_completion(messages)
        """
        try:
            # Normalize content to messages list
            if isinstance(content, str):
                # Simple string: wrap as user message
                messages = [{"role": "user", "content": content}]
            elif isinstance(content, dict):
                # Single message dict: wrap in list
                messages = [content]
            elif isinstance(content, list):
                # Already a list of messages
                messages = content
            else:
                raise OllamaError(
                    f"Invalid content type. Expected str, dict, or list, got {type(content)}"
                )
            
            logger.info(f"Sending {len(messages)} message(s) to model: {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            result = response.choices[0].message.content
            logger.info("Successfully received response from model")
            return result
        except Exception as e:
            raise OllamaError(f"Error calling model: {e}")
