"""
Pytest fixtures for offline testing with mocked external APIs.

These fixtures enable tests to run without hitting real APIs, making them
fast (~100x faster), reproducible, and reliable regardless of external service availability.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture
def mock_weather_api():
    """
    Mock OpenWeatherMap API responses.
    
    Replaces requests.get to simulate successful weather API calls.
    Returns realistic weather data for testing.
    """
    with patch('src.tools.weather_tool.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "London",
            "sys": {"country": "GB"},
            "main": {
                "temp": 15.2,
                "feels_like": 14.8,
                "humidity": 72,
                "pressure": 1013
            },
            "weather": [
                {
                    "main": "Cloudy",
                    "description": "overcast clouds"
                }
            ],
            "wind": {"speed": 3.5},
            "clouds": {"all": 90}
        }
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_ollama_api():
    """
    Mock Ollama LLM API responses.
    
    Replaces OpenAI client to simulate successful LLM calls.
    Returns realistic responses and token counts for testing.
    """
    with patch('src.providers.ollama_provider.OpenAI') as mock_client:
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "London is currently cloudy with a temperature of 15°C, "
            "with humidity at 72% and a gentle breeze at 3.5 m/s. "
            "Perfect weather for a light jacket!"
        )
        mock_response.usage.prompt_tokens = 45
        mock_response.usage.completion_tokens = 22
        mock_response.usage.total_tokens = 67
        
        mock_client.return_value.chat.completions.create.return_value = mock_response
        yield mock_client


@pytest.fixture
def mock_web_search_api():
    """
    Mock DuckDuckGo web search API responses.
    
    Replaces requests.get for web search to simulate successful search calls.
    Returns realistic search results for testing.
    """
    with patch('src.tools.web_search_tool.requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Python Best Practices - Real Python",
                    "link": "https://realpython.com/python-best-practices",
                    "snippet": "Follow PEP 8, use type hints, write tests, and maintain clear documentation..."
                },
                {
                    "title": "Clean Code Principles",
                    "link": "https://example.com/clean-code",
                    "snippet": "Code is read more often than written. Optimize for readability first."
                },
                {
                    "title": "Python Coding Standards",
                    "link": "https://example.com/coding-standards",
                    "snippet": "Comprehensive guide to writing production-quality Python code..."
                }
            ]
        }
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def config_for_testing():
    """
    Provide test configuration without requiring real API keys.
    
    Returns a ConfigManager instance with test values.
    """
    from src.utils.config_loader import ConfigManager
    
    config = ConfigManager("configs/config.yaml")
    # Set test values
    config._config["runtime"] = {"orchestration": "langchain"}
    config._config["env"] = {
        "ollama_api_key": "test-key",
        "ollama_base_url": "http://localhost:11434",
        "openweather_api_key": "test-key",
        "openweather_base_url": "https://api.openweathermap.org/data/2.5"
    }
    return config


@pytest.fixture
def mock_all_apis(mock_weather_api, mock_ollama_api, mock_web_search_api):
    """
    Fixture combining all API mocks for comprehensive integration testing.
    
    Use this when testing workflows that call multiple APIs.
    """
    return {
        "weather": mock_weather_api,
        "ollama": mock_ollama_api,
        "web_search": mock_web_search_api
    }
