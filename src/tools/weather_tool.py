import logging
from typing import Optional, Dict, Any
import requests
from utils.config_loader import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO)
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
        Initialize WeatherClient with configuration

        Args:
            config_manager: ConfigManager instance with loaded configuration

        Raises:
            WeatherConfigError: If configuration is invalid
            WeatherAPIError: If unable to connect to weather API
        """
        self.config = config_manager
        self.api_key = config_manager.get("weather.api_key")
        self.base_url = config_manager.get("weather.base_url")

        if not self.api_key or not self.base_url:
            raise WeatherConfigError(
                "Weather API key and base URL must be configured"
            )

        # Validate connection to API
        self._validate_connection()
        logger.info("WeatherClient initialized successfully")

    def _validate_connection(self) -> None:
        """
        Check if weather API is accessible
        
        Raises:
            WeatherAPIError: If unable to connect
        """
        try:
            # Test connection with a simple query (using a known city)
            response = requests.get(
                f"{self.base_url}/weather?q=London&appid={self.api_key}&units=metric",
                timeout=5
            )
            if response.status_code != 200:
                raise WeatherAPIError(
                    f"Weather API returned status {response.status_code}: {response.text}"
                )
            logger.info("Successfully connected to Weather API")
        except requests.ConnectionError:
            raise WeatherAPIError(
                f"Cannot connect to Weather API at {self.base_url}. "
                "Make sure the API endpoint is accessible."
            )
        except requests.Timeout:
            raise WeatherAPIError(
                f"Weather API at {self.base_url} is not responding (timeout)"
            )

    def get_temperature(self, city: str, units: str = "imperial") -> Dict[str, Any]:
        """
        Get temperature and weather condition for a city
        
        Args:
            city: Name of the city to get weather for
            units: Temperature units - 'metric' (Celsius), 'imperial' (Fahrenheit), or 'standard' (Kelvin)
                   Defaults to 'imperial'
            
        Returns:
            dict: Weather data containing city, temperature, condition, and other details
                  {
                      "city": str,
                      "temperature": float,
                      "condition": str,
                      "feels_like": float,
                      "humidity": int,
                      "pressure": int
                  }
            
        Raises:
            CityNotFoundError: If city is not found
            WeatherAPIError: If API request fails
            
        Examples:
            client = WeatherClient(config_manager)
            weather = client.get_temperature("New York")
            weather = client.get_temperature("London", units="metric")
        """
        if not city or not isinstance(city, str) or not city.strip():
            raise ValueError("City name must be a non-empty string")

        try:
            url = (
                f"{self.base_url}/weather"
                f"?q={city.strip()}&appid={self.api_key}&units={units}"
            )
            
            logger.info(f"Fetching weather for city: {city}")
            response = requests.get(url, timeout=5)

            if response.status_code == 404:
                raise CityNotFoundError(f"City '{city}' not found")
            elif response.status_code != 200:
                raise WeatherAPIError(
                    f"Weather API error: {response.status_code} - {response.text}"
                )

            data = response.json()

            # Extract relevant weather data
            weather_data = {
                "city": data.get("name"),
                "country": data.get("sys", {}).get("country"),
                "temperature": data.get("main", {}).get("temp"),
                "feels_like": data.get("main", {}).get("feels_like"),
                "humidity": data.get("main", {}).get("humidity"),
                "pressure": data.get("main", {}).get("pressure"),
                "condition": data.get("weather", [{}])[0].get("main"),
                "description": data.get("weather", [{}])[0].get("description"),
                "units": units
            }

            logger.info(f"Successfully retrieved weather for {city}")
            return weather_data

        except requests.Timeout:
            raise WeatherAPIError(
                f"Weather API request for '{city}' timed out"
            )
        except requests.RequestException as e:
            raise WeatherAPIError(f"Error fetching weather data: {e}")
        except (KeyError, ValueError) as e:
            raise WeatherAPIError(f"Error parsing weather API response: {e}")


# Legacy function for backward compatibility
def get_temperature(city: str) -> Dict[str, Any]:
    """
    Legacy function for backward compatibility.
    Get temperature and weather condition for a city using default configuration.
    
    Args:
        city: Name of the city to get weather for
        
    Returns:
        dict: Weather data with city, temperature, and condition
        
    Raises:
        WeatherConfigError: If configuration fails
        CityNotFoundError: If city is not found
        WeatherAPIError: If API request fails
    """
    config_manager = ConfigManager("../configs/config.yaml")
    client = WeatherClient(config_manager)
    result = client.get_temperature(city)
    
    # Return simplified result for backward compatibility
    return {
        "city": result["city"],
        "temperature": result["temperature"],
        "condition": result["condition"]
    }