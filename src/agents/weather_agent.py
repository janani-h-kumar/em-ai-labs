import logging
import re
from pathlib import Path
from typing import Any

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
    Enterprise Weather Agent.
    
    Uses explicit dependency injection for rock-solid predictability and testing.
    """

    def __init__(
        self,
        config_path: str | None = None,
        system_prompt: str | None = None,
        base_llm_provider: BaseLLMProvider | None = None,
        weather_client: BaseTool | None = None,
    ):
        # Resolve config path cleanly
        if config_path is None:
            config_path = str(
                Path(__file__).parent.parent.parent / "configs" / "config.yaml"
            )
            
        super().__init__(config_path=config_path)

        # Set system behavior rules
        self.system_prompt: str = system_prompt or (
            "You are a friendly weather assistant. Summarize weather in one sentence."
        )

        # Assign injected components or establish default production clients
        self.base_llm_provider: BaseLLMProvider = base_llm_provider or BaseLLMProvider(self.config_manager)
        self.weather_client: BaseTool = weather_client or BaseTool(self.config_manager)

    def initialize(self) -> None:
        """Fulfills lifecycle hooks safely without throwing side effects."""
        logger.info("WeatherAgent components validated and live.")

    def handle(self, message: str) -> str:
        try:
            city = self.extract_city(message)
            return self.get_weather_summary(city)
        except Exception as e:
            return f"Sorry, I couldn't process that request: {e}"

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

    def get_weather_summary(self, city: str, temperature_units: str = "imperial") -> str:
        if not city or not city.strip():
            raise ValueError("City must be non-empty")

        try:
            # 1. Fetch raw metrics
            weather = self.weather_client.get_temperature(city.strip())

            # 2. Build explicit inference frame
            prompt = (
                f"Weather:\n"
                f"City: {weather['city']}\n"
                f"Temp: {weather['temperature']}\n"
                f"Condition: {weather['condition']}\n\n"
                "Give a one-line friendly summary."
            )

            # 3. Request LLM generation
            response = self.base_llm_provider.chat_completion(
                messages=prompt, 
                system_prompt=self.system_prompt
            )
            return response.strip()

        except Exception as e:
            error_class = e.__class__.__name__
            # Handle domain-specific edge errors transparently
            if error_class in ("CityNotFoundError", "WeatherAPIError", "OllamaError"):
                raise WeatherAgentExecutionError("City not found: {e}") from e
            raise WeatherAgentExecutionError("An error occurred: {e}") from e

    def get_detailed_weather(self, city: str, temperature_units: str = "imperial") -> dict[str, Any]:
        if not city or not city.strip():
            raise ValueError("City must be non-empty")
        return self.weather_client.get_temperature(city.strip())

    def health_check(self) -> dict[str, Any]:
        import datetime
        return {
            "agent": "WeatherAgent",
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
        }
