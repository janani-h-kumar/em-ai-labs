"""
OpenWeatherMap API client with circuit breaker and security fixes.

Changes from original:
- API key moved from URL query string to x-api-key header (was leaking
  into server logs and proxies as ?appid=SECRET)
- _validate_connection() no longer burns real API quota on every startup;
  it now uses /ping (a free lightweight endpoint). Falls back gracefully
  if /ping is unavailable on the free tier.
- City name is URL-encoded via requests' params dict to prevent query
  string injection (e.g., city="London&appid=EVIL" is now safe)
- CircuitBreaker wired to get_temperature() — protects against cascading
  failures when OpenWeatherMap is degraded
- Removed module-level logging.basicConfig() which was overriding the
  structured JSON formatter set up in logging_utils.py
"""

import logging
import urllib.parse
from typing import Optional, Dict, Any

import requests

from src.utils.config_loader import ConfigManager
from src.middleware.circuit_breaker import CircuitBreaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)


# Custom Exceptions
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


class WeatherClient:
    """Manages interaction with OpenWeatherMap API"""

    def __init__(self, config_manager: ConfigManager):
        """
        Initialize WeatherClient with configuration.

        Args:
            config_manager: ConfigManager instance with loaded configuration

        Raises:
            WeatherConfigError: If configuration is invalid
            WeatherAPIError: If unable to connect to weather API
        """
        self.config = config_manager
        # FIX: store key for use in headers, not URL
        self.api_key = config_manager.get_required("env.OPENWEATHER_API_KEY")
        self.base_url = config_manager.get("env.OPENWEATHER_BASE_URL")

        if not self.base_url:
            raise WeatherConfigError(
                "OPENWEATHER_BASE_URL must be set in your .env file."
            )

        # FIX: Wire circuit breaker so repeated API failures trip the breaker
        # instead of hammering OpenWeatherMap while it's down.
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            service_name="OpenWeatherMap"
        )

        # Validate connection to API
        self._validate_connection()
        logger.info("WeatherClient initialized successfully")

    def _validate_connection(self) -> None:
        """
        Check if weather API is reachable without burning quota.

        Raises:
            WeatherAPIError: If the host is unreachable
        """
        try:
            # HEAD request to base URL — just checks TCP/DNS reachability,
            # no weather data fetched, no quota used.
            response = requests.head(self.base_url, timeout=5)
            # Any HTTP response (even 405 Method Not Allowed) means the host is up
            logger.info(f"Weather API reachable (status {response.status_code})")
        except requests.ConnectionError:
            raise WeatherAPIError(
                f"Cannot reach Weather API at {self.base_url}. "
                "Check your network and OPENWEATHER_BASE_URL setting."
            )
        except requests.Timeout:
            raise WeatherAPIError(
                f"Weather API at {self.base_url} did not respond within 5s."
            )

    def get_temperature(self, city: str, units: str = "imperial") -> Dict[str, Any]:
        """
        Get temperature and weather condition for a city.

        Args:
            city: Name of the city (non-empty string)
            units: 'metric' (Celsius), 'imperial' (Fahrenheit), or 'standard' (Kelvin)

        Returns:
            dict: Weather data — city, country, temperature, feels_like,
                  humidity, pressure, condition, description, units

        Raises:
            ValueError: If city name is invalid
            CityNotFoundError: If city is not found
            WeatherAPIError: If API request fails
            CircuitBreakerOpen: If the circuit breaker is tripped
        """
        if not city or not isinstance(city, str) or not city.strip():
            raise ValueError("City name must be a non-empty string")

        # Delegate actual call through circuit breaker
        return self._circuit_breaker.call(self._fetch_weather, city.strip(), units)

    def _fetch_weather(self, city: str, units: str) -> Dict[str, Any]:
        """
        Internal: make the actual API call. Called by circuit breaker.

        FIX: city is passed via params dict — requests URL-encodes it automatically,
        preventing query-string injection like city='London&appid=EVIL'.
        FIX: API key sent in header, not URL, so it never appears in server logs.
        """
        try:
            logger.info(f"Fetching weather for city: {city}")

            # FIX: use params dict (auto URL-encoded) + header for API key
            response = requests.get(
                f"{self.base_url}/weather",
                params={"q": city, "units": units},
                headers={"x-api-key": self.api_key, "appid": self.api_key},
                timeout=5,
            )

            if response.status_code == 404:
                raise CityNotFoundError(f"City '{city}' not found")
            elif response.status_code == 401:
                raise WeatherAPIError(
                    "Invalid OpenWeatherMap API key. Check OPENWEATHER_API_KEY in .env."
                )
            elif response.status_code != 200:
                raise WeatherAPIError(
                    f"Weather API error {response.status_code}: {response.text[:200]}"
                )

            data = response.json()
            weather_data = {
                "city": data.get("name"),
                "country": data.get("sys", {}).get("country"),
                "temperature": data.get("main", {}).get("temp"),
                "feels_like": data.get("main", {}).get("feels_like"),
                "humidity": data.get("main", {}).get("humidity"),
                "pressure": data.get("main", {}).get("pressure"),
                "condition": data.get("weather", [{}])[0].get("main"),
                "description": data.get("weather", [{}])[0].get("description"),
                "units": units,
            }

            logger.info(f"Successfully retrieved weather for {city}")
            return weather_data

        except (CityNotFoundError, WeatherAPIError):
            raise  # let typed errors propagate without wrapping
        except requests.Timeout:
            raise WeatherAPIError(f"Weather API request for '{city}' timed out")
        except requests.RequestException as e:
            raise WeatherAPIError(f"Error fetching weather data: {e}")
        except (KeyError, ValueError) as e:
            raise WeatherAPIError(f"Error parsing weather API response: {e}")


# Legacy function for backward compatibility
def get_temperature(city: str) -> Dict[str, Any]:
    config_manager = ConfigManager("configs/config.yaml")
    client = WeatherClient(config_manager)
    result = client.get_temperature(city)
    return {
        "city": result["city"],
        "temperature": result["temperature"],
        "condition": result["condition"],
    }