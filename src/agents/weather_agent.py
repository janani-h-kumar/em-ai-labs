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
            "You are a helpful weather assistant. Always include the specific "
            "temperature, feels-like temperature, and humidity in your response — "
            "never reply with only a vague description like 'cloudy' or 'pleasant' "
            "without the numbers. Keep it concise and friendly, 1-3 sentences. "
            "If the conversation history includes earlier questions, use them for context "
            "(e.g. 'what about tomorrow' refers to the city already discussed)."
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

    async def get_weather_summary(self, city: str, task=None, context=None) -> str:
        """
        Fetch weather and generate summary.

        [Pillar 1] Now accepts the optional task/context so the weather
        prompt can be assembled via BaseAgent._build_messages() — meaning
        a follow-up like "what about tomorrow?" carries the previously
        discussed city/forecast as context instead of being answered cold.
        """
        if not city or not city.strip():
            raise ValueError("city must be a non-empty string")

        try:
            weather_data = self.weather_tool.get_temperature(city)

            # FIX: prompt was only passing description + temperature, so the
            # LLM had nothing else to report. Pass every field so the summary
            # can mention feels-like, humidity, pressure, and condition —
            # the model can only ground its answer in what it's given.
            unit_symbol = "°F" if weather_data.units == "imperial" else "°C"
            weather_prompt = (
                f"Weather in {weather_data.city}, {weather_data.country}: "
                f"{weather_data.condition} ({weather_data.description}). "
                f"Temperature is {weather_data.temperature}{unit_symbol}, "
                f"feels like {weather_data.feels_like}{unit_symbol}. "
                f"Humidity is {weather_data.humidity}%, "
                f"pressure is {weather_data.pressure} hPa. "
                f"Write a short, friendly summary that includes the actual "
                f"temperature, feels-like value, and humidity — not just a "
                f"general description like 'cloudy' or 'pleasant'."
            )

            if task is not None and context is not None:
                messages = self._build_messages(task, context, extra_content=weather_prompt)
                summary = self.base_llm_provider.chat_completion(
                    messages, system_prompt=self.system_prompt
                )
            else:
                # Fallback for direct calls without orchestration context
                # (e.g. unit tests calling get_weather_summary() in isolation).
                summary = self.base_llm_provider.chat_completion(
                    weather_prompt, system_prompt=self.system_prompt
                )

            return summary

        except CityNotFoundError as e:
            raise WeatherAgentExecutionError(f"City not found: {city}") from e

        except Exception as e:
            logger.exception("Failed getting weather summary")
            raise WeatherAgentExecutionError(str(e)) from e

    async def handle(self, task, context):
        query = task.description or ""
        city = self.extract_city(query)
        return await self.get_weather_summary(city, task=task, context=context)
