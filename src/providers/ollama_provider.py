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
from typing import Any, TypedDict, cast

import requests
from openai import OpenAI

from src.providers.base_provider import BaseLLMProvider, HealthStatus

logger = logging.getLogger(__name__)


class ModelEntry(TypedDict):
    name: str


class PsResponse(TypedDict, total=False):
    models: list[ModelEntry]


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


class OllamaClient(BaseLLMProvider):
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
            raise OllamaConfigError("OLLAMA_BASE_URL is not set. Add it to your .env file.")

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
        logger.info("OllamaClient initialized with model: %s", self.model)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _build_base_url(self, host: str | None) -> str | None:
        if not host:
            return None
        host = host.rstrip("/")
        return host if host.endswith("/v1") else f"{host}/v1"

    def _validate_connection(self) -> None:
        """Verify Ollama server is reachable."""
        try:
            response = requests.get(
                f"{self.base_url.replace('/v1', '')}/api/tags",
                timeout=5,
            )
            if response.status_code != 200:
                raise OllamaConnectionError(
                    "Ollama server returned status %s", response.status_code
                )
            logger.info("Successfully connected to Ollama server")
        except requests.ConnectionError as e:
            raise OllamaConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Is Ollama running? Try: ollama serve"
            ) from e
        except requests.Timeout as e:
            raise OllamaConnectionError(
                f"Ollama server at {self.base_url} did not respond within 5s."
            ) from e

    def _auto_select_model(self) -> str | None:
        """Return the first running model, or first available model."""
        try:
            for endpoint in ("/api/ps", "/api/tags"):
                resp = requests.get(
                    f"{self.base_url.replace('/v1', '')}{endpoint}",
                    timeout=5,
                )
                resp.raise_for_status()

                data = cast(dict, resp.json())
                models_raw = data.get("models", [])

                # explicit narrowing
                models: list[str] = []

                for m in models_raw:
                    if isinstance(m, dict) and "name" in m:
                        models.append(str(m["name"]))

                if models:
                    return models[0]

        except requests.RequestException:
            pass

        return None

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
                logger.info("Auto-selected model: %s", self.model)
                return

            response = requests.get(
                f"{self.base_url.replace('/v1', '')}/api/tags",
                timeout=5,
            )
            response.raise_for_status()
            available = [m["name"] for m in response.json().get("models", [])]

            if not available:
                raise ModelNotFoundError("No models available. Run: ollama pull <model-name>")

            model_found = any(self.model in m or m.startswith(self.model) for m in available)
            if not model_found:
                raise ModelNotFoundError(
                    f"Model '{self.model}' not found. "
                    f"Available: {', '.join(available)}. "
                    f"Run: ollama pull {self.model}"
                )

            logger.info("Model '%s' confirmed available", self.model)

        except requests.RequestException as e:
            raise OllamaConnectionError(f"Error checking model availability: {e}") from e

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def chat_completion(
        self,
        messages: str | list[dict[Any, Any]],
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Send a message to the model and return its response.

        Args:
            messages: str (simple prompt), dict (single message), or
                     list of message dicts (multi-turn conversation)

        Returns:
            str: Model response text

        Raises:
            OllamaError: On API failure
        """
        try:
            if isinstance(messages, str):
                messages = [{"role": "user", "content": messages}]
            elif isinstance(messages, dict):
                messages = [messages]
            elif isinstance(messages, list):
                messages = messages
            else:
                raise OllamaError(
                    f"Invalid messages type {type(messages)}. Expected str, dict, or list."
                )

            logger.info("Sending %s message(s) to model: %s", len(messages), self.model)
            request_kwargs = dict(model=self.model, messages=messages)
            if max_tokens is not None:
                request_kwargs["max_tokens"] = max_tokens
            response = self.client.chat.completions.create(**request_kwargs)
            result = str(response.choices[0].message.content)
            token_usage = getattr(response, "usage", None)
            if token_usage is not None:
                try:
                    prompt_tokens = int(token_usage.get("prompt_tokens", 0))
                    completion_tokens = int(token_usage.get("completion_tokens", 0))
                    total_tokens = int(token_usage.get("total_tokens", 0))
                except Exception:
                    prompt_tokens = completion_tokens = total_tokens = 0
            else:
                prompt_tokens = completion_tokens = total_tokens = 0

            logger.info(
                "Successfully received response from model",
                extra={
                    "extra_data": {
                        "model_name": self.model,
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    }
                },
            )
            return result

        except OllamaError:
            raise
        except Exception as e:
            raise OllamaError(f"Error calling model '{self.model}': {e}") from e

    def health_check(self) -> HealthStatus:
        """Checks if the local Ollama instance is reachable."""
        try:
            import requests

            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=2,
            )

            return HealthStatus(
                status="healthy" if response.status_code == 200 else "degraded",
                provider="OllamaClient",
                status_code=response.status_code,
            )

        except Exception as e:
            return HealthStatus(status="degraded", provider="OllamaClient", error=str(e))


Client = OllamaClient
