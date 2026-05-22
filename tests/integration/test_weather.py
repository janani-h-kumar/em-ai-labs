from unittest.mock import Mock

import pytest

from src.agents.weather_agent import WeatherAgent, WeatherAgentExecutionError
from src.tools.weather_tool import CityNotFoundError

# ------------------------------------------------------------------
# FIXTURE (clean DI - NO __new__)
# ------------------------------------------------------------------

@pytest.fixture
def agent():
    return WeatherAgent(config_path=None, base_llm_provider=mock_llm, weather_client=mock_weather)

@pytest.fixture
def mock_llm():
    return Mock()

@pytest.fixture
def mock_weather():
    return Mock()


# ------------------------------------------------------------------
# CITY EXTRACTION TESTS
# ------------------------------------------------------------------

def test_extract_city_basic(agent):
    assert agent.extract_city("Weather in London") == "London"


def test_extract_city_multi_word(agent):
    assert agent.extract_city("Weather in New York today") == "New York"


def test_extract_city_empty(agent):
    assert agent.extract_city("") == "New York"


def test_extract_city_none_like(agent):
    assert agent.extract_city("   ") == "New York"


# ------------------------------------------------------------------
# SUMMARY FLOW TESTS
# ------------------------------------------------------------------

def test_weather_summary_success(agent):
    agent.weather_client.get_temperature.return_value = {
        "city": "London",
        "temperature": 15,
        "condition": "Cloudy",
    }

    agent.ollama_client.chat_completion.return_value = "Nice weather"

    result = agent.get_weather_summary("London")

    assert result == "Nice weather"


def test_city_not_found(agent):
    agent.weather_client.get_temperature.side_effect = CityNotFoundError("missing")

    with pytest.raises(WeatherAgentExecutionError):
        agent.get_weather_summary("FakeCity")


def test_empty_city_raises(agent):
    with pytest.raises(ValueError):
        agent.get_weather_summary("")
