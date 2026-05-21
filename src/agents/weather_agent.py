import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any

from agents.base_agent import BaseAgent
from providers.base_provider import BaseLLMProvider
from tools.base_tool import BaseTool


logger = logging.getLogger(__name__)

class WeatherAgentError(Exception):
    pass


class WeatherAgentInitError(WeatherAgentError):
    pass


class WeatherAgentExecutionError(WeatherAgentError):
    pass


class WeatherAgent(BaseAgent):
    """
    Weather Agent

    Key improvement in this refactor:
    - Dependency injection supported for testability
    - Production behavior unchanged
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        system_prompt: Optional[str] = None,
        base_llm_provider: Optional[BaseLLMProvider] = None,
        weather_client: Optional[BaseTool] = None,
    ):
        if config_path is None:
            config_path = str(
                Path(__file__).parent.parent.parent / "configs" / "config.yaml"
            )

        self.system_prompt = system_prompt or (
            "You are a friendly weather assistant. "
            "Summarize weather in one sentence."
        )

        # DI hooks (IMPORTANT for tests)
        self._external_weather_client = weather_client
        self._external_base_llm_provider = base_llm_provider

        super().__init__(config_path=config_path)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        logger.info("Initializing WeatherAgent...")

        try:
            # Standardize on base_llm_provider
            self.base_llm_provider = (
                self._external_base_llm_provider
                or BaseLLMProvider(self.config_manager)
            )

            self.weather_client = (
                self._external_weather_client
                or BaseTool(self.config_manager)
            )

            logger.info(
                f"LLM Provider ready (model={getattr(self.base_llm_provider, 'model_name', 'unknown')})"
            )
            logger.info("Weather client ready")

        except Exception as e:
            raise WeatherAgentInitError(f"Unexpected init error: {e}")

    # ------------------------------------------------------------------
    # Core handler
    # ------------------------------------------------------------------

    def handle(self, message: str) -> str:
        try:
            city = self.extract_city(message)
            return self.get_weather_summary(city)
        except Exception as e:
            logger.error(f"handle error: {e}")
            return f"Sorry, I couldn't process request: {e}"

    # ------------------------------------------------------------------
    # City extraction (kept lightweight, no spaCy dependency)
    # ------------------------------------------------------------------

    def extract_city(self, message: str) -> str:
        if not message or not message.strip():
            return "New York"

        message = message.strip()

        filler = {
            "what", "whats", "what's", "how", "weather", "is",
            "the", "in", "at", "for", "today", "tomorrow", "now",
            "can", "you", "please"
        }

        candidates = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', message)
        filtered = [c for c in candidates if c.lower() not in filler]

        if filtered:
            return filtered[0]

        return "New York"

    # ------------------------------------------------------------------
    # Weather summary
    # ------------------------------------------------------------------

    def get_weather_summary(self, city: str, temperature_units: str = "imperial") -> str:
        if not city or not city.strip():
            raise ValueError("City must be non-empty")

        try:
            # Step 1: Use the injected weather client tool
            weather = self.weather_client.get_temperature(city.strip())

            prompt = (
                f"Weather:\n"
                f"City: {weather['city']}\n"
                f"Temp: {weather['temperature']}\n"
                f"Condition: {weather['condition']}\n\n"
                "Give a one-line friendly summary."
            )

            # FIX: Use self.base_llm_provider instead of the missing self.ollama_client
            # Also passes system_prompt if your BaseLLMProvider supports it!
            response = self.base_llm_provider.chat_completion(
                messages=prompt, 
                system_prompt=self.system_prompt
            )
            return response.strip()

        except Exception as e:
            # Dynamic check for exception types to avoid crashing if imports don't exist
            error_classname = e.__class__.__name__
            if error_classname in ("CityNotFoundError", "WeatherAPIError", "OllamaError"):
                raise WeatherAgentExecutionError(f"Dependency error ({error_classname}): {e}")
            raise WeatherAgentExecutionError(str(e))

    # ------------------------------------------------------------------
    # Detailed weather
    # ------------------------------------------------------------------

    def get_detailed_weather(self, city: str, temperature_units: str = "imperial") -> Dict[str, Any]:
        if not city or not city.strip():
            raise ValueError("City must be non-empty")

        return self.weather_client.get_temperature(city.strip())

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        import datetime

        return {
            "agent": "WeatherAgent",
            "initialized": self.is_initialized(),
            "status": "healthy" if self.is_initialized() else "unhealthy",
            "timestamp": datetime.datetime.now().isoformat(),
        }


# ----------------------------------------------------------------------
# Legacy helper (unchanged)
# ----------------------------------------------------------------------

def weather_agent(city: str) -> str:
    agent = WeatherAgent()
    agent.initialize()  # Added to prevent uninitialized execution bugs
    return agent.get_weather_summary(city)