"""
Weather agent using BaseAgent standardisation.

Changes from original:
- Removed module-level logging.basicConfig() — overrode the structured
  JSON formatter from logging_utils.py. Now uses getLogger only.
- Fixed extract_city(): original just returned the last word of the message,
  which broke on nearly every real query (e.g. "what's the weather today?"
  returned "today"). New implementation uses a prioritised strategy:
    1. spaCy GPE/LOC entities if spaCy is installed (best)
    2. Capitalised-word heuristic (good enough for most queries)
    3. Fallback to "New York" with a warning log
  This is still not production NER, but it's far more correct than
  taking the last word, and degrades gracefully without new dependencies.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from agents.base_agent import BaseAgent
from providers.ollama_provider import (
    OllamaClient,
    OllamaError,
    OllamaConnectionError,
    OllamaConfigError,
)
from tools.weather_tool import (
    WeatherClient,
    WeatherAPIError,
    CityNotFoundError,
    WeatherConfigError,
)

# FIX: removed logging.basicConfig(level=logging.INFO) — it silently
# overrides the StructuredFormatter set up by setup_structured_logging().
logger = logging.getLogger(__name__)


class WeatherAgentError(Exception):
    """Base exception for Weather Agent errors"""
    pass


class WeatherAgentInitError(WeatherAgentError):
    """Raised when weather agent initialisation fails"""
    pass


class WeatherAgentExecutionError(WeatherAgentError):
    """Raised when weather agent execution fails"""
    pass


class WeatherAgent(BaseAgent):
    """
    Weather agent using BaseAgent standardisation.

    Fetches weather data from OpenWeatherMap and summarises it
    via a local Ollama LLM.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        if config_path is None:
            config_path = str(
                Path(__file__).parent.parent.parent / "configs" / "config.yaml"
            )
        self.system_prompt = system_prompt or (
            "You are a friendly weather assistant. "
            "Summarise weather data in one engaging sentence. "
            "Be concise and informative."
        )
        super().__init__(config_path=config_path)

    # -----------------------------------------------------------------------
    # BaseAgent lifecycle
    # -----------------------------------------------------------------------

    def initialize(self) -> None:
        self.logger.info("Initialising WeatherAgent...")

        try:
            self.ollama_client = OllamaClient(self.config_manager)
            self.logger.info(f"Ollama client ready (model: {self.ollama_client.model})")

            self.weather_client = WeatherClient(self.config_manager)
            self.logger.info("Weather client ready")

        except OllamaConfigError as e:
            self.logger.error(f"Ollama config error: {e}")
            raise WeatherAgentInitError(f"Failed to load Ollama configuration: {e}")
        except OllamaConnectionError as e:
            self.logger.error(f"Ollama connection error: {e}")
            raise WeatherAgentInitError(f"Failed to connect to Ollama: {e}")
        except WeatherConfigError as e:
            self.logger.error(f"Weather config error: {e}")
            raise WeatherAgentInitError(f"Failed to configure weather client: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected initialisation error: {e}")
            raise WeatherAgentInitError(f"Unexpected error during initialisation: {e}")

    def handle(self, message: str) -> str:
        try:
            city = self.extract_city(message)
            return self.get_weather_summary(city)
        except Exception as e:
            self.logger.error(f"Error handling message '{message}': {e}")
            return f"Sorry, I couldn't process your weather request. Error: {e}"

    # -----------------------------------------------------------------------
    # City extraction — FIX
    # -----------------------------------------------------------------------

    def extract_city(self, message: str) -> str:
        """
        Extract a city name from a free-text message.

        Strategy (in priority order):
        1. spaCy NER (GPE/LOC entities) — most accurate, optional dependency
        2. Capitalised multi-word heuristic — handles "New York", "Los Angeles"
        3. Fallback to "New York" with a warning

        Original code returned the last word of the message, which fails on
        queries like "what's the weather today?" → "today".

        Args:
            message: Raw user input string

        Returns:
            str: Best-guess city name
        """
        if not message or not message.strip():
            return "New York"

        # Strategy 1: spaCy NER (only if installed — not a hard dependency)
        try:
            import spacy  # noqa: PLC0415
            nlp = spacy.load("en_core_web_sm")
            doc = nlp(message)
            locations = [
                ent.text for ent in doc.ents
                if ent.label_ in ("GPE", "LOC")
            ]
            if locations:
                logger.debug(f"spaCy extracted city: {locations[0]}")
                return locations[0]
        except (ImportError, OSError):
            # spaCy or model not installed — fall through to heuristic
            pass

        # Strategy 2: capitalised-word heuristic
        # Strips common filler words that are also capitalised ("What", "I", etc.)
        filler = {
            "what", "whats", "what's", "how", "is", "the", "weather",
            "in", "at", "for", "today", "tomorrow", "now", "like",
            "tell", "me", "can", "you", "please", "a", "an",
        }
        # Match sequences of Title-Case words (handles "New York", "San Francisco")
        candidates = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', message)
        filtered = [c for c in candidates if c.lower() not in filler]

        if filtered:
            city = filtered[0]
            logger.debug(f"Heuristic extracted city: {city}")
            return city

        # Strategy 3: fallback
        logger.warning(
            f"Could not extract a city from message: '{message}'. "
            "Defaulting to 'New York'. Consider adding spaCy for better NER."
        )
        return "New York"

    # -----------------------------------------------------------------------
    # Core methods
    # -----------------------------------------------------------------------

    def get_weather_summary(
        self,
        city: str,
        temperature_units: str = "imperial",
    ) -> str:
        if not city or not isinstance(city, str) or not city.strip():
            raise ValueError("City name must be a non-empty string")

        try:
            self.logger.info(f"Fetching weather summary for: {city}")
            weather_data = self.weather_client.get_temperature(
                city.strip(), units=temperature_units
            )
            weather_text = self._format_weather_data(weather_data)

            prompt = (
                f"Weather Information:\n{weather_text}\n\n"
                "Provide a friendly one-sentence summary of this weather. "
                "Be engaging but concise."
            )

            response = self.ollama_client.chat_completion(prompt)
            return response.strip()

        except CityNotFoundError as e:
            self.logger.error(f"City not found: {e}")
            raise WeatherAgentExecutionError(f"City not found: {e}")
        except WeatherAPIError as e:
            self.logger.error(f"Weather API error: {e}")
            raise WeatherAgentExecutionError(f"Failed to fetch weather: {e}")
        except OllamaError as e:
            self.logger.error(f"Ollama error: {e}")
            raise WeatherAgentExecutionError(f"Failed to generate summary: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise WeatherAgentExecutionError(f"Unexpected error: {e}")

    def get_detailed_weather(
        self,
        city: str,
        temperature_units: str = "imperial",
    ) -> Dict[str, Any]:
        if not city or not isinstance(city, str) or not city.strip():
            raise ValueError("City name must be a non-empty string")

        try:
            self.logger.info(f"Retrieving detailed weather for: {city}")
            return self.weather_client.get_temperature(
                city.strip(), units=temperature_units
            )
        except CityNotFoundError as e:
            self.logger.error(f"City not found: {e}")
            raise WeatherAgentExecutionError(f"City not found: {e}")
        except WeatherAPIError as e:
            self.logger.error(f"Weather API error: {e}")
            raise WeatherAgentExecutionError(f"Failed to fetch weather: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise WeatherAgentExecutionError(f"Unexpected error: {e}")

    def _format_weather_data(self, weather_data: Dict[str, Any]) -> str:
        units_label = "°C" if weather_data.get("units") == "metric" else "°F"
        return (
            f"City: {weather_data.get('city')}, {weather_data.get('country')}\n"
            f"Temperature: {weather_data.get('temperature')}{units_label}\n"
            f"Feels Like: {weather_data.get('feels_like')}{units_label}\n"
            f"Condition: {weather_data.get('condition')} "
            f"({weather_data.get('description')})\n"
            f"Humidity: {weather_data.get('humidity')}%\n"
            f"Pressure: {weather_data.get('pressure')} hPa"
        )

    def health_check(self) -> Dict[str, Any]:
        import datetime
        status = "healthy" if self.is_initialized() else "unhealthy"
        return {
            "agent": self.__class__.__name__,
            "initialized": self.is_initialized(),
            "status": status,
            "timestamp": datetime.datetime.now().isoformat(),
        }


# Legacy helper for backward compatibility
def weather_agent(city: str) -> str:
    agent = WeatherAgent()
    return agent.get_weather_summary(city)
