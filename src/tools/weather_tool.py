"""OpenWeatherMap tool with execution-time API telemetry."""

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


class WeatherInput(BaseModel):
    city: str = Field(description="The city to look up weather for, e.g. Seattle")


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


class WeatherError(Exception):
    """Base exception for weather API failures."""


class WeatherConfigError(WeatherError):
    """Raised for invalid weather configuration."""


class WeatherAPIError(WeatherError):
    """Raised for weather API failures."""


class WeatherAuthenticationError(WeatherAPIError):
    """Raised when the weather API rejects authentication."""


class CityNotFoundError(WeatherError):
    """Raised when the requested city cannot be found."""


class WeatherClient:
    """Raw weather API client.

    Construction validates configuration only. It deliberately does not call
    the external service. API reachability/authentication is an execution
    concern and is captured by ``tool.api_request``.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager
        self.api_key = config_manager.get_required("env.OPENWEATHER_API_KEY")
        self.base_url = config_manager.get("env.OPENWEATHER_BASE_URL")

        if not self.base_url:
            raise WeatherConfigError("OPENWEATHER_BASE_URL must be set in your .env file.")

        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            service_name="OpenWeatherMap",
        )
        logger.info("WeatherClient initialized")

    def get_temperature(self, city: str, units: str = "imperial") -> WeatherResult:
        if not city or not isinstance(city, str) or not city.strip():
            raise ValueError("City name must be a non-empty string")
        result = self._circuit_breaker.call(self._fetch_weather, city.strip(), units)
        return cast(WeatherResult, result)

    def _fetch_weather(self, city: str, units: str) -> WeatherResult:
        start_time = time.perf_counter()
        with create_span(
            "tool.api_request",
            **{
                "tool.name": "weather_tool",
                "tool_name": "weather_tool",
                "tool": "weather_tool",
                "api_service": "openweathermap",
                "http_method": "GET",
                "outcome": "unknown",
            },
        ) as span:
            try:
                response = requests.get(
                    f"{self.base_url.rstrip('/')}/weather",
                    params={"q": city, "units": units},
                    headers={"x-api-key": self.api_key, "appid": self.api_key},
                    timeout=5,
                )
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("api_latency_ms", duration_ms)
                span.set_attribute("latency_ms", duration_ms)
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("response_size_bytes", len(response.content or b""))

                if response.status_code == 401:
                    error = WeatherAuthenticationError("Invalid OpenWeatherMap API key.")
                    span.set_attribute("error.type", type(error).__name__)
                    span.set_attribute("outcome", "error")
                    span.record_exception(error)
                    span.set_status(otel_trace.StatusCode.ERROR, str(error))
                    raise error

                if response.status_code == 404:
                    error = CityNotFoundError(f"City '{city}' not found")
                    span.set_attribute("error.type", type(error).__name__)
                    span.set_attribute("outcome", "error")
                    span.record_exception(error)
                    span.set_status(otel_trace.StatusCode.ERROR, str(error))
                    raise error

                if response.status_code != 200:
                    error = WeatherAPIError(f"Weather API error {response.status_code}")
                    span.set_attribute("error.type", type(error).__name__)
                    span.set_attribute("outcome", "error")
                    span.record_exception(error)
                    span.set_status(otel_trace.StatusCode.ERROR, str(error))
                    raise error

                data = response.json()
                result = WeatherResult(
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
                span.set_attribute("outcome", "success")
                return result

            except requests.Timeout as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("api_latency_ms", duration_ms)
                span.set_attribute("error.type", type(exc).__name__)
                span.set_attribute("outcome", "error")
                span.record_exception(exc)
                span.set_status(otel_trace.StatusCode.ERROR, str(exc))
                raise WeatherAPIError(f"Weather API request for '{city}' timed out") from exc

            except requests.RequestException as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("api_latency_ms", duration_ms)
                span.set_attribute("error.type", type(exc).__name__)
                span.set_attribute("outcome", "error")
                span.record_exception(exc)
                span.set_status(otel_trace.StatusCode.ERROR, str(exc))
                raise WeatherAPIError(f"Error fetching weather data: {exc}") from exc

            except (KeyError, TypeError, ValueError) as exc:
                span.set_attribute("error.type", type(exc).__name__)
                span.set_attribute("outcome", "error")
                span.record_exception(exc)
                span.set_status(otel_trace.StatusCode.ERROR, str(exc))
                raise WeatherAPIError(f"Error parsing weather API response: {exc}") from exc


class WeatherTool(BaseTool):
    """LangChain/framework interface for the weather client."""

    name = "weather_tool"
    description = "Get current weather for a city."
    args_schema = WeatherInput

    def __init__(self, config_manager: ConfigManager):
        super().__init__(config_manager)
        self.client = WeatherClient(config_manager)

    def _run(self, *args, **kwargs) -> str:
        city = kwargs.get("city") or (args[0] if args else None)
        if not city:
            raise ValueError("City parameter is required.")
        units = kwargs.get("units", "imperial")
        return str(self.client.get_temperature(city=city, units=units))

    def get_temperature(self, city: str, units: str = "imperial") -> WeatherResult:
        if not city:
            raise ValueError("City parameter is required.")

        start_time = time.perf_counter()
        with create_span(
            "tool.call",
            **{
                "tool.name": self.name,
                "tool_name": self.name,
                "tool": self.name,
                "operation": "get_temperature",
                "outcome": "unknown",
            },
        ) as span:
            try:
                result = self.client.get_temperature(city=city, units=units)
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("latency_ms", duration_ms)
                span.set_attribute("outcome", "success")
                span.set_attribute("response_size_bytes", len(str(result).encode("utf-8")))
                return result
            except Exception as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
                span.set_attribute("duration_ms", duration_ms)
                span.set_attribute("latency_ms", duration_ms)
                span.set_attribute("outcome", "error")
                span.set_attribute("error.type", type(exc).__name__)
                span.record_exception(exc)
                span.set_status(otel_trace.StatusCode.ERROR, str(exc))
                raise
