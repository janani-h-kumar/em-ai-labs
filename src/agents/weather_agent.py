"""
WeatherAgent implementation using explicit Dependency Injection.
"""

import logging
import re
from typing import Any

from src.agents.base_agent import (
    AgentExecutionError,
    AgentInitError,
    BaseAgent,
)
from src.tools.weather_tool import CityNotFoundError
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
    - weather_client
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        base_llm_provider: Any,
        weather_client: Any,
    ) -> None:
        self.base_llm_provider = base_llm_provider
        self.weather_client = weather_client

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

        if self.weather_client is None:
            raise AgentInitError("weather_client is required")

        self.system_prompt = (
            "You are a helpful weather assistant. Provide concise and friendly weather summaries."
        )

        logger.info("WeatherAgent initialized successfully")

    def handle(self, message: str) -> str:
        """
        Main router entrypoint.
        """
        try:
            city = self.extract_city(message)
            return self.get_weather_summary(city)

        except WeatherAgentExecutionError:
            raise

        except Exception as e:
            logger.exception("WeatherAgent handle() failed")
            raise WeatherAgentExecutionError(str(e)) from e

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

    def get_weather_summary(self, city: str) -> str:
        """
        Fetch weather and generate summary.
        """
        if not city or not city.strip():
            raise ValueError("city must be a non-empty string")

        try:
            weather_data = self.weather_client.get_temperature(city)

            prompt = (
                f"Weather in {weather_data['city']}: "
                f"{weather_data['description']}, "
                f"temperature {weather_data['temperature']}°."
            )

            summary = self.base_llm_provider.chat_completion(prompt)

            return str(summary)

        except CityNotFoundError as e:
            raise WeatherAgentExecutionError(f"City not found: {city}") from e

        except Exception as e:
            logger.exception("Failed getting weather summary")
            raise WeatherAgentExecutionError(str(e)) from e
