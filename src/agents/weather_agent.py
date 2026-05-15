import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherAgentError(Exception):
    """Base exception for Weather Agent errors"""
    pass


class WeatherAgentInitError(WeatherAgentError):
    """Raised when weather agent initialization fails"""
    pass


class WeatherAgentExecutionError(WeatherAgentError):
    """Raised when weather agent execution fails"""
    pass


class WeatherAgent(BaseAgent):
    """
    Weather agent using BaseAgent standardization.

    This agent fetches weather data from OpenWeather and summarizes it
    through Ollama, while inheriting base agent lifecycle behavior.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        if config_path is None:
            config_path = str(Path(__file__).parent.parent.parent / "configs" / "config.yaml")
        self.system_prompt = system_prompt or (
            "You are a friendly weather assistant. "
            "Summarize weather data in one engaging sentence. "
            "Be concise and informative."
        )
        super().__init__(config_path=config_path)

    def initialize(self) -> None:
        self.logger.info("Initializing WeatherAgent...")

        try:
            self.ollama_client = OllamaClient(self.config_manager)
            self.logger.info(f"Ollama client initialized (model: {self.ollama_client.model})")

            self.weather_client = WeatherClient(self.config_manager)
            self.logger.info("Weather client initialized")

        except OllamaConfigError as e:
            self.logger.error(f"Ollama configuration error: {e}")
            raise WeatherAgentInitError(f"Failed to load Ollama configuration: {e}")
        except OllamaConnectionError as e:
            self.logger.error(f"Ollama connection error: {e}")
            raise WeatherAgentInitError(f"Failed to connect to Ollama: {e}")
        except WeatherConfigError as e:
            self.logger.error(f"Weather configuration error: {e}")
            raise WeatherAgentInitError(f"Failed to configure weather client: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected initialization error: {e}")
            raise WeatherAgentInitError(f"Unexpected error during initialization: {e}")

    def handle(self, message: str) -> str:
        try:
            city = self.extract_city(message)
            return self.get_weather_summary(city)
        except Exception as e:
            self.logger.error(f"Error handling message '{message}': {e}")
            return f"Sorry, I couldn't process your weather request. Error: {e}"

    def extract_city(self, message: str) -> str:
        words = [word.strip('.,?!') for word in message.strip().split() if word.strip()]
        return words[-1] if words else "New York"

    def get_weather_summary(
        self,
        city: str,
        temperature_units: str = "imperial",
    ) -> str:
        if not city or not isinstance(city, str) or not city.strip():
            raise ValueError("City name must be a non-empty string")

        try:
            self.logger.info(f"Fetching weather summary for: {city}")
            weather_data = self.weather_client.get_temperature(city.strip(), units=temperature_units)
            weather_text = self._format_weather_data(weather_data)

            prompt = f"""
Weather Information:
{weather_text}

Provide a friendly one-sentence summary of this weather. Be engaging but concise."""

            response = self.ollama_client.chat_completion(prompt)
            return response.strip()
        except CityNotFoundError as e:
            self.logger.error(f"City not found: {e}")
            raise WeatherAgentExecutionError(f"City not found: {e}")
        except WeatherAPIError as e:
            self.logger.error(f"Weather API error: {e}")
            raise WeatherAgentExecutionError(f"Failed to fetch weather: {e}")
        except OllamaError as e:
            self.logger.error(f"Ollama error during summarization: {e}")
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
            return self.weather_client.get_temperature(city.strip(), units=temperature_units)
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
            f"Current Temperature: {weather_data.get('temperature')}{units_label}\n"
            f"Feels Like: {weather_data.get('feels_like')}{units_label}\n"
            f"Condition: {weather_data.get('condition')} ({weather_data.get('description')})\n"
            f"Humidity: {weather_data.get('humidity')}%\n"
            f"Pressure: {weather_data.get('pressure')} hPa"
        )

    def health_check(self) -> Dict[str, Any]:
        status = "healthy" if self.is_initialized() else "unhealthy"
        return {
            "agent": self.__class__.__name__,
            "initialized": self.is_initialized(),
            "status": status,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }


# Legacy helper for backward compatibility

def weather_agent(city: str) -> str:
    agent = WeatherAgent()
    return agent.get_weather_summary(city)
