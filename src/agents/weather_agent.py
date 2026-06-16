"""
WeatherAgent implementation using explicit Dependency Injection.
"""

import logging
import re

from src.agents.base_agent import (
    AgentExecutionError,
    AgentInitError,
    BaseAgent,
)
from src.providers.base_provider import BaseLLMProvider
from src.tools.weather_tool import CityNotFoundError, WeatherTool
from src.utils.config_loader import ConfigManager

logger = logging.getLogger(__name__)


class WeatherAgentExecutionError(AgentExecutionError):
    """Raised when weather agent execution fails."""


class WeatherAgent(BaseAgent):
    """
    Weather agent with explicit dependency injection.

    Dependencies are passed in from outside:
    - config_manager
    - base_llm_provider
    - weather_tool
    """

    # Agent metadata
    name = "weather_agent"
    description = "Provides weather information"
    capabilities = [
        "weather",
        "forecast",
        "temperature",
        "rain",
        "snow",
    ]

    def __init__(
        self,
        config_manager: ConfigManager,
        base_llm_provider: BaseLLMProvider,
        weather_tool: WeatherTool,
    ) -> None:
        self.base_llm_provider = base_llm_provider
        self.weather_tool = weather_tool

        super().__init__(config_manager)

    # ------------------------------------------------------------------
    # BaseAgent contract
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        Validate injected dependencies and initialize prompts/state.
        """
        if self.base_llm_provider is None:
            raise AgentInitError("base_llm_provider is required")

        if self.weather_tool is None:
            raise AgentInitError("weather_tool is required")

        self.system_prompt = (
            "You are a helpful weather assistant. Provide concise and friendly weather summaries."
        )

        logger.info("WeatherAgent initialized successfully")

    # ------------------------------------------------------------------
    # Domain logic
    # ------------------------------------------------------------------

    def extract_city(self, message: str) -> str:
        """
        Extract city name from user message.

        Falls back to New York if extraction fails.
        """
        if not message or not message.strip():
            return "New York"

        patterns = [
            r"in\s+([A-Za-z\s]+)",
            r"for\s+([A-Za-z\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)

            if match:
                city = match.group(1).strip()

                city = re.sub(
                    r"\b(today|now|please|weather|temperature)\b",
                    "",
                    city,
                    flags=re.IGNORECASE,
                ).strip()

                if city:
                    return city.title()

        return "New York"

    async def get_weather_summary(self, city: str) -> str:
        """
        Fetch weather and generate summary.
        """
        if not city or not city.strip():
            raise ValueError("city must be a non-empty string")

        try:
            weather_data = self.weather_tool.get_temperature(city)

            prompt = (
                f"Weather in {weather_data.city}: "
                f"{weather_data.description}, "
                f"temperature {weather_data.temperature}°."
            )

            summary = self.base_llm_provider.chat_completion(prompt)

            return summary

        except CityNotFoundError as e:
            raise WeatherAgentExecutionError(f"City not found: {city}") from e

        except Exception as e:
            logger.exception("Failed getting weather summary")
            raise WeatherAgentExecutionError(str(e)) from e

    async def handle(self, task, context):
        query = task.description or ""
        return await self.get_weather_summary(self.extract_city(query))
