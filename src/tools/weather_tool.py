"""
OpenWeatherMap API client with circuit breaker and security fixes.
Integrated with BaseTool architectural pattern.
"""

import logging
import time
from typing import cast

import requests
from opentelemetry import trace as otel_trace
from pydantic import BaseModel, Field

from src.middleware.circuit_breaker import CircuitBreaker
from src.observability.tracing import create_span
from src.tools.base_tool import BaseTool
from src.utils.config_loader import ConfigManager

logger = logging.getLogger(__name__)


# --- 1. Schema Input Definition ---
class WeatherInput(BaseModel):
    city: str = Field(
        description="The name of the city to look up the weather for, e.g., 'New York'"
    )


class WeatherResult(BaseModel):
    city: str
    country: str
    temperature: float
    feels_like: float
    humidity: int
    pressure: int
    condition: str
    description: str
    units: str


# Custom Exceptions (Compliant with N818: All end with 'Error' suffix)
class WeatherError(Exception):
    """Base exception for Weather API-related errors"""

    pass


class WeatherConfigError(WeatherError):
    """Raised when weather configuration loading or validation fails"""

    pass


class WeatherAPIError(WeatherError):
    """Raised when Weather API request fails"""

    pass


class CityNotFoundError(WeatherError):
    """Raised when the specified city is not found"""

    pass


# --- 2. The Core API Client (Pure Data Fetcher) ---
class WeatherClient:
    """Manages raw interaction with OpenWeatherMap API with circuit breaking."""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.api_key = config_manager.get_required("env.OPENWEATHER_API_KEY")
        self.base_url = config_manager.get("env.OPENWEATHER_BASE_URL")

        if not self.base_url:
            raise WeatherConfigError("OPENWEATHER_BASE_URL must be set in your .env file.")

        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60, service_name="OpenWeatherMap"
        )

        self._validate_connection()
        logger.info("WeatherClient initialized successfully")

    def _validate_connection(self) -> None:
        try:
            response = requests.head(self.base_url, timeout=5)
            logger.info("Weather API reachable (status %s)", response.status_code)
        except requests.ConnectionError as e:
            # FIXED B904: Added explicit exception chaining via 'from e'
            raise WeatherAPIError(
                f"Cannot reach Weather API at {self.base_url}. Check network."
            ) from e
        except requests.Timeout as e:
            # FIXED B904: Added explicit exception chaining via 'from e'
            raise WeatherAPIError(
                f"Weather API at {self.base_url} did not respond within 5s."
            ) from e

    def get_temperature(self, city: str, units: str = "imperial") -> WeatherResult:
        if not city or not isinstance(city, str) or not city.strip():
            raise ValueError("City name must be a non-empty string")
        result = self._circuit_breaker.call(self._fetch_weather, city.strip(), units)
        return cast(WeatherResult, result)

    def _fetch_weather(self, city: str, units: str) -> WeatherResult:
        with create_span(
            "tool.api_request",
            tool_name="weather_tool",
            api_service="openweathermap",
            http_method="GET",
            url=f"{self.base_url}/weather",
            city=city,
            units=units,
        ) as span:
            start_time = time.perf_counter()
            try:
                logger.info("Fetching weather for city: %s", city)
                response = requests.get(
                    f"{self.base_url}/weather",
                    params={"q": city, "units": units},
                    headers={"x-api-key": self.api_key, "appid": self.api_key},
                    timeout=5,
                )
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("api_latency_ms", duration_ms)

                if response.status_code == 404:
                    raise CityNotFoundError(f"City '{city}' not found")
                elif response.status_code == 401:
                    raise WeatherAPIError("Invalid OpenWeatherMap API key.")
                elif response.status_code != 200:
                    raise WeatherAPIError(f"Weather API error {response.status_code}")

                data = response.json()
                return WeatherResult(
                    city=data.get("name"),
                    country=data.get("sys", {}).get("country"),
                    temperature=data.get("main", {}).get("temp"),
                    feels_like=data.get("main", {}).get("feels_like"),
                    humidity=data.get("main", {}).get("humidity"),
                    pressure=data.get("main", {}).get("pressure"),
                    condition=data.get("weather", [{}])[0].get("main"),
                    description=data.get("weather", [{}])[0].get("description"),
                    units=units,
                )
            except (CityNotFoundError, WeatherAPIError) as e:
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                raise
            except requests.Timeout as e:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("api_latency_ms", duration_ms)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                span.record_exception(e)
                # FIXED B904: Added explicit exception chaining via 'from e'
                raise WeatherAPIError(f"Weather API request for '{city}' timed out") from e
            except requests.RequestException as e:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("api_latency_ms", duration_ms)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise WeatherAPIError(f"Error fetching weather data: {e}") from e
            except (KeyError, ValueError) as e:
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise WeatherAPIError(f"Error parsing weather API response: {e}") from e


# --- 3. The LangChain Framework Agent Tool Wrapper ---
class WeatherTool(BaseTool):
    """LangChain integration interface for the Weather Client."""

    name = "weather_tool"
    description = "Get current weather for a city. Input: city name. Output: temperature, condition, humidity."
    args_schema = WeatherInput

    def __init__(self, config_manager: ConfigManager):
        # Pass config_manager to the abstract parent BaseTool initialization contract
        super().__init__(config_manager)
        # Instantiate the data fetcher safely once on startup
        self.client = WeatherClient(config_manager)

    def _run(self, *args, **kwargs) -> str:
        # Extract validated argument strings safely
        city = kwargs.get("city") or (args[0] if args else None)
        if not city:
            raise ValueError("City parameter is required.")

        # Execute via the local initialized client instance
        return str(self.client.get_temperature(city=city))

    def get_temperature(
        self,
        city: str,
        units: str = "imperial",
    ) -> WeatherResult:
        # Extract validated argument strings safely
        if not city:
            raise ValueError("City parameter is required.")

        with create_span(
            "tool.execute",
            tool_name=self.name,
            operation="get_temperature",
            city=city,
            units=units,
        ) as span:
            start_time = time.perf_counter()
            try:
                result = self.client.get_temperature(city=city, units=units)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("tool_latency_ms", duration_ms)
                return result
            except Exception as e:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("tool_latency_ms", duration_ms)
                span.set_status(otel_trace.StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise
