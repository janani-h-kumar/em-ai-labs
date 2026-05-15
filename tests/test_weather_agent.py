import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.weather_agent import (
    WeatherAgent,
    WeatherAgentInitError,
    WeatherAgentExecutionError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_agent_initialization():
    """Test WeatherAgent initialization"""
    print("\n" + "="*70)
    print(" Testing WeatherAgent Initialization")
    print("="*70)
    
    try:
        agent = WeatherAgent()
        print(f"\n✅ Agent initialized successfully")
        print(f"   Model: {agent.ollama_client.model}")
        print(f"   Weather API: {agent.weather_client.base_url}")
        print(f"   System Prompt: {agent.system_prompt[:60]}...\n")
        return agent, 0
    except WeatherAgentInitError as e:
        logger.error(f"Agent initialization failed: {e}")
        return None, 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return None, 1


def test_weather_summary(agent):
    """Test getting weather summaries"""
    print("\n" + "="*70)
    print(" Testing Weather Summary Generation")
    print("="*70)
    
    if not agent:
        print("❌ Agent not initialized")
        return 1
    
    try:
        test_cities = ["New York", "London", "Paris"]
        
        for city in test_cities:
            try:
                print(f"\n📍 {city}:")
                print("   ⏳ Fetching weather and generating summary...")
                summary = agent.get_weather_summary(city)
                print(f"   ✅ {summary}\n")
            except WeatherAgentExecutionError as e:
                print(f"   ❌ Error: {e}\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


def test_detailed_weather(agent):
    """Test getting detailed weather data"""
    print("\n" + "="*70)
    print(" Testing Detailed Weather Data")
    print("="*70)
    
    if not agent:
        print("❌ Agent not initialized")
        return 1
    
    try:
        city = "New York"
        
        print(f"\n📍 {city} (Detailed Weather - Metric):")
        weather_metric = agent.get_detailed_weather(city, temperature_units="metric")
        print_weather_details(weather_metric)
        
        print(f"\n📍 {city} (Detailed Weather - Imperial):")
        weather_imperial = agent.get_detailed_weather(city, temperature_units="imperial")
        print_weather_details(weather_imperial)
        
        return 0
        
    except WeatherAgentExecutionError as e:
        logger.error(f"Agent execution failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


def test_error_handling(agent):
    """Test error handling for edge cases"""
    print("\n" + "="*70)
    print(" Testing Error Handling")
    print("="*70)
    
    if not agent:
        print("❌ Agent not initialized")
        return 1
    
    test_cases = [
        ("InvalidCityXYZ123", "Invalid city"),
        ("", "Empty string"),
        (None, "None value"),
    ]
    
    passed = 0
    failed = 0
    
    for city_input, description in test_cases:
        try:
            if city_input is None:
                raise ValueError("City name must be a non-empty string")
            
            print(f"\n⏳ Testing with {description}...", end=" ")
            agent.get_weather_summary(city_input)
            print("❌ Should have raised an error")
            failed += 1
            
        except (WeatherAgentExecutionError, ValueError) as e:
            print(f"✅ Correctly caught error")
            failed += 0
            passed += 1
        except Exception as e:
            print(f"✅ Caught {type(e).__name__}")
            passed += 1
    
    print(f"\n✅ Error handling: {passed} tests passed, {failed} failed\n")
    return failed


def test_custom_system_prompt(agent):
    """Test agent with custom system prompt"""
    print("\n" + "="*70)
    print(" Testing Custom System Prompt")
    print("="*70)
    
    try:
        custom_prompt = (
            "You are a weather announcer for a sports broadcast. "
            "Describe the weather in one exciting sentence suitable for a stadium announcer."
        )
        
        print(f"\n🎤 Custom prompt: '{custom_prompt[:50]}...'\n")
        
        custom_agent = WeatherAgent(system_prompt=custom_prompt)
        
        city = "New York"
        print(f"📍 {city} with custom prompt:")
        print("   ⏳ Generating sports broadcast style summary...")
        summary = custom_agent.get_weather_summary(city)
        print(f"   ✅ {summary}\n")
        
        return 0
        
    except WeatherAgentInitError as e:
        logger.error(f"Agent initialization failed: {e}")
        return 1
    except WeatherAgentExecutionError as e:
        logger.error(f"Agent execution failed: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


def print_weather_details(weather_data):
    """Helper to print weather details"""
    for key, value in weather_data.items():
        if value is not None:
            formatted_key = key.replace('_', ' ').title()
            if key == "temperature" or key == "feels_like":
                print(f"   {formatted_key}: {value}° ({weather_data.get('units', 'unknown')})")
            else:
                print(f"   {formatted_key}: {value}")


def main():
    """Run all weather agent tests"""
    print("\n🌦️  Weather Agent Test Suite")
    
    # Test 1: Initialization
    agent, result1 = test_agent_initialization()
    
    # Test 2: Weather summaries
    result2 = test_weather_summary(agent) if agent else 1
    
    # Test 3: Detailed weather
    result3 = test_detailed_weather(agent) if agent else 1
    
    # Test 4: Error handling
    result4 = test_error_handling(agent) if agent else 1
    
    # Test 5: Custom system prompt
    result5 = test_custom_system_prompt(agent) if agent else 1
    
    # Summary
    print("\n" + "="*70)
    print(" Test Summary")
    print("="*70)
    total_failures = result1 + result2 + result3 + result4 + result5
    if total_failures == 0:
        print("✅ All tests passed!\n")
        return 0
    else:
        print(f"⚠️  {total_failures} test(s) failed\n")
        return 1


if __name__ == "__main__":
    exit(main())
