"""
Ollama LLM provider client.

Changes from original:
- Removed module-level logging.basicConfig() which was silently overriding
  the structured JSON formatter configured in logging_utils.py. All log
  output now flows through the root handler set up at startup.
- Added timeout to ChatOllama/OpenAI client calls so a slow local model
  cannot hang the process indefinitely.
- OLLAMA_API_KEY is now treated as optional (local Ollama doesn't need one).
  A dummy fallback value is used so the OpenAI-compat client initialises
  without error, matching how Ollama actually works.
"""

import logging
from typing import Optional, Union, List, Dict

import requests
from openai import OpenAI

# FIX: Removed logging.basicConfig(level=logging.INFO) — it overrides
# the StructuredFormatter set up in logging_utils.py and breaks JSON log
# aggregation in production (Datadog, CloudWatch, etc.).
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class OllamaClient:
    """Manages interaction with a local Ollama server via the OpenAI-compat API."""
    @property
    def model_name(self):
        return self.model

    def __init__(self, config_manager):
        """
        Initialize OllamaClient with configuration.

        Args:
            config_manager: ConfigManager instance

        Raises:
            OllamaConfigError: If base URL is missing
            OllamaConnectionError: If server is unreachable
            ModelNotFoundError: If specified model is unavailable
        """
        self.config = config_manager
        self.host = config_manager.get("env.OLLAMA_BASE_URL") or "http://localhost:11434"
        self.base_url = self._build_base_url(self.host)

        if not self.base_url:
            raise OllamaConfigError(
                "OLLAMA_BASE_URL is not set. Add it to your .env file."
            )

        # FIX: OLLAMA_API_KEY is optional for local Ollama — use a harmless
        # placeholder if unset so the OpenAI client doesn't raise on init.
        self.api_key = config_manager.get("env.OLLAMA_API_KEY") or "ollama"

        self.model = config_manager.get("env.OLLAMA_MODEL")

        # Validate connection and model availability
        self._validate_connection()
        self._validate_model_exists()

        # FIX: pass timeout so slow models don't hang the process forever.
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=60.0,  # seconds; adjust per your model's expected latency
        )
        logger.info(f"OllamaClient initialized with model: {self.model}")

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_base_url(self, host: Optional[str]) -> Optional[str]:
        if not host:
            return None
        host = host.rstrip('/')
        return host if host.endswith('/v1') else f"{host}/v1"

    def _validate_connection(self) -> None:
        """Verify Ollama server is reachable."""
        try:
            response = requests.get(
                f"{self.base_url.replace('/v1', '')}/api/tags",
                timeout=5,
            )
            if response.status_code != 200:
                raise OllamaConnectionError(
                    f"Ollama server returned status {response.status_code}"
                )
            logger.info("Successfully connected to Ollama server")
        except requests.ConnectionError:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Try: ollama serve"
            )
        except requests.Timeout:
            raise OllamaConnectionError(
                f"Ollama server at {self.base_url} did not respond within 5s."
            )

    def _validate_model_exists(self) -> None:
        """Check the configured model is available; auto-select if unset."""
        try:
            if not self.model:
                self.model = self._auto_select_model()
                if not self.model:
                    raise ModelNotFoundError(
                        "No model specified and no models found on the server. "
                        "Run: ollama pull <model-name>"
                    )
                logger.info(f"Auto-selected model: {self.model}")
                return

            response = requests.get(
                f"{self.base_url.replace('/v1', '')}/api/tags",
                timeout=5,
            )
            response.raise_for_status()
            available = [m["name"] for m in response.json().get("models", [])]

            if not available:
                raise ModelNotFoundError(
                    "No models available. Run: ollama pull <model-name>"
                )

            model_found = any(
                self.model in m or m.startswith(self.model)
                for m in available
            )
            if not model_found:
                raise ModelNotFoundError(
                    f"Model '{self.model}' not found. "
                    f"Available: {', '.join(available)}. "
                    f"Run: ollama pull {self.model}"
                )

            logger.info(f"Model '{self.model}' confirmed available")

        except requests.RequestException as e:
            raise OllamaConnectionError(f"Error checking model availability: {e}")

    def _auto_select_model(self) -> Optional[str]:
        """Return the first running model, or first available model."""
        try:
            for endpoint in ("/api/ps", "/api/tags"):
                resp = requests.get(
                    f"{self.base_url.replace('/v1', '')}{endpoint}",
                    timeout=5,
                )
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
                if models:
                    return models[0]
        except requests.RequestException:
            pass
        return None

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def chat_completion(self, content: Union[str, Dict, List[Dict]]) -> str:
        """
        Send a message to the model and return its response.

        Args:
            content: str (simple prompt), dict (single message), or
                     list of message dicts (multi-turn conversation)

        Returns:
            str: Model response text

        Raises:
            OllamaError: On API failure
        """
        try:
            if isinstance(content, str):
                messages = [{"role": "user", "content": content}]
            elif isinstance(content, dict):
                messages = [content]
            elif isinstance(content, list):
                messages = content
            else:
                raise OllamaError(
                    f"Invalid content type {type(content)}. "
                    "Expected str, dict, or list."
                )

            logger.info(f"Sending {len(messages)} message(s) to model: {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            result = response.choices[0].message.content
            logger.info("Successfully received response from model")
            return result

        except OllamaError:
            raise
        except Exception as e:
            raise OllamaError(f"Error calling model '{self.model}': {e}")

Client = OllamaClient