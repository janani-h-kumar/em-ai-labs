import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.weather_tool import (
    WeatherClient,
    WeatherConfigManager,
    get_temperature,
    CityNotFoundError,
    WeatherAPIError,
    WeatherConfigError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_legacy_function():
    """Test the legacy get_temperature function for backward compatibility"""
    print("\n" + "="*70)
    print(" Testing Legacy get_temperature() Function")
    print("="*70)
    
    try:
        result = get_temperature("New York")
        print(f"\n✅ Result:")
        print(f"   City: {result['city']}")
        print(f"   Temperature: {result['temperature']}°F")
        print(f"   Condition: {result['condition']}\n")
    except WeatherConfigError as e:
        logger.error(f"Configuration Error: {e}")
        return 1
    except CityNotFoundError as e:
        logger.error(f"City Error: {e}")
        return 1
    except WeatherAPIError as e:
        logger.error(f"API Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
    
    return 0


def test_weather_client():
    """Test the new WeatherClient class with detailed weather data"""
    print("\n" + "="*70)
    print(" Testing WeatherClient with Detailed Data")
    print("="*70)
    
    try:
        # Initialize configuration and client
        config_manager = WeatherConfigManager("configs/config.yaml")
        client = WeatherClient(config_manager)
        
        # Test with different cities and units
        cities_to_test = [
            ("London", "metric"),
            ("Tokyo", "metric"),
            ("Sydney", "imperial"),
        ]
        
        for city, units in cities_to_test:
            weather_data = client.get_temperature(city, units=units)
            
            print(f"\n📍 {city}:")
            print(f"   Country: {weather_data['country']}")
            print(f"   Temperature: {weather_data['temperature']}° ({weather_data['units']})")
            print(f"   Feels Like: {weather_data['feels_like']}°")
            print(f"   Condition: {weather_data['condition']} - {weather_data['description']}")
            print(f"   Humidity: {weather_data['humidity']}%")
            print(f"   Pressure: {weather_data['pressure']} hPa")
        
        print("\n✅ All tests passed!\n")
        return 0
        
    except WeatherConfigError as e:
        logger.error(f"Configuration Error: {e}")
        return 1
    except CityNotFoundError as e:
        logger.error(f"City Error: {e}")
        return 1
    except WeatherAPIError as e:
        logger.error(f"API Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


def test_error_handling():
    """Test error handling with invalid cities"""
    print("\n" + "="*70)
    print(" Testing Error Handling")
    print("="*70)
    
    try:
        config_manager = WeatherConfigManager("configs/config.yaml")
        client = WeatherClient(config_manager)
        
        # Try to get weather for non-existent city
        try:
            client.get_temperature("InvalidCityXYZ123")
            print("❌ Should have raised CityNotFoundError")
            return 1
        except CityNotFoundError as e:
            print(f"✅ Correctly caught CityNotFoundError: {e}")
        
        # Try with empty string
        try:
            client.get_temperature("")
            print("❌ Should have raised ValueError")
            return 1
        except ValueError as e:
            print(f"✅ Correctly caught ValueError: {e}")
        
        print("\n✅ Error handling tests passed!\n")
        return 0
        
    except WeatherConfigError as e:
        logger.error(f"Configuration Error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


def main():
    """Run all tests"""
    print("\n🌡️  Weather Tool Test Suite")
    
    # Test 1: Legacy function
    result1 = test_legacy_function()
    
    # Test 2: WeatherClient with detailed data
    result2 = test_weather_client()
    
    # Test 3: Error handling
    result3 = test_error_handling()
    
    # Return combined result
    return result1 or result2 or result3


if __name__ == "__main__":
    exit(main())