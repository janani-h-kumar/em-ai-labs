"""
Pytest fixtures for offline testing with mocked external APIs.

Changes from original:
- Fixed mock_web_search_api: original returned results[].link but the actual
  DuckDuckGo API returns results[].FirstURL. Tests passed but would have
  failed against the real API — a false green. Now matches the real contract.
- config_for_testing now uses uppercase env keys (OLLAMA_API_KEY, etc.) to
  match the real ConfigManager behaviour and avoid key-casing bugs in tests.
- Added explicit docstrings explaining what each fixture simulates.
"""

import sys
import types
from unittest.mock import Mock, patch

import pytest

# Lightweight stubs for optional external dependencies to allow offline unit tests.
# These create minimal modules/classes expected by the code under test so import
# time does not fail when packages (langchain, anthropic, langchain_core) are
# not installed in the test environment.
_stubs = {
    "anthropic": types.ModuleType("anthropic"),
    "langchain": types.ModuleType("langchain"),
    "langchain.agents": types.ModuleType("langchain.agents"),
    "langchain_core": types.ModuleType("langchain_core"),
    "langchain_core.tools": types.ModuleType("langchain_core.tools"),
}

for name, mod in _stubs.items():
    if name not in sys.modules:
        sys.modules[name] = mod

# Minimal symbols expected by imports in the codebase
sys.modules["langchain.agents"].AgentExecutor = type("AgentExecutor", (), {})
sys.modules["langchain.agents"].create_tool_calling_agent = lambda *a, **k: None


def _tool_factory(name: str, description: str = "", args_schema=None, func=None):
    return types.SimpleNamespace(
        name=name, description=description, args_schema=args_schema, func=func
    )


sys.modules["langchain_core.tools"].Tool = _tool_factory
# chat_history
if "langchain_core.chat_history" not in sys.modules:
    sys.modules["langchain_core.chat_history"] = types.ModuleType("langchain_core.chat_history")
sys.modules["langchain_core.chat_history"].InMemoryChatMessageHistory = type(
    "InMemoryChatMessageHistory", (), {"messages": []}
)

# prompts
if "langchain_core.prompts" not in sys.modules:
    sys.modules["langchain_core.prompts"] = types.ModuleType("langchain_core.prompts")
sys.modules["langchain_core.prompts"].ChatPromptTemplate = type(
    "ChatPromptTemplate", (), {"from_messages": staticmethod(lambda msgs: None)}
)
sys.modules["langchain_core.prompts"].MessagesPlaceholder = type("MessagesPlaceholder", (), {})

# runnables.history
if "langchain_core.runnables.history" not in sys.modules:
    sys.modules["langchain_core.runnables.history"] = types.ModuleType(
        "langchain_core.runnables.history"
    )
sys.modules["langchain_core.runnables.history"].RunnableWithMessageHistory = type(
    "RunnableWithMessageHistory", (), {}
)

# langchain_ollama stub
if "langchain_ollama" not in sys.modules:
    sys.modules["langchain_ollama"] = types.ModuleType("langchain_ollama")
sys.modules["langchain_ollama"].ChatOllama = type(
    "ChatOllama", (), {"__init__": lambda self, *a, **k: None, "invoke": lambda self, msg: "pong"}
)


@pytest.fixture
def mock_weather_api():
    """
    Mock OpenWeatherMap API responses.

    Patches requests.get in weather_tool so no real HTTP calls are made.
    Returns a realistic London weather payload.
    """
    with patch("src.tools.weather_tool.requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "London",
            "sys": {"country": "GB"},
            "main": {
                "temp": 15.2,
                "feels_like": 14.8,
                "humidity": 72,
                "pressure": 1013,
            },
            "weather": [{"main": "Cloudy", "description": "overcast clouds"}],
            "wind": {"speed": 3.5},
            "clouds": {"all": 90},
        }
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_ollama_api():
    """
    Mock Ollama LLM API responses.

    Patches the OpenAI client used by OllamaClient so no model inference
    is needed to run tests.
    """
    with patch("src.providers.ollama_provider.OpenAI") as mock_client:
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = "London is currently cloudy at 15°C — pack a light jacket!"
        mock_response.usage.prompt_tokens = 45
        mock_response.usage.completion_tokens = 22
        mock_response.usage.total_tokens = 67

        mock_client.return_value.chat.completions.create.return_value = mock_response
        yield mock_client


@pytest.fixture
def mock_web_search_api():
    """
    Mock DuckDuckGo web search API responses.

    FIX: original mock returned results[].link but the real DuckDuckGo
    instant-answer API returns results[].FirstURL. Mismatched keys meant
    tests passed while the real code would have silently returned empty URLs.
    """
    with patch("src.tools.web_search_tool.requests.get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        # FIX: use 'FirstURL' (real API key), not 'link' (wrong key)
        mock_response.json.return_value = {
            "RelatedTopics": [
                {
                    "Text": "Python Best Practices — Follow PEP 8, use type hints, write tests.",
                    "FirstURL": "https://realpython.com/python-best-practices",
                },
                {
                    "Text": "Clean Code Principles — Code is read more often than written.",
                    "FirstURL": "https://example.com/clean-code",
                },
                {
                    "Text": "Python Coding Standards — Comprehensive guide to production Python.",
                    "FirstURL": "https://example.com/coding-standards",
                },
            ]
        }
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def config_for_testing():
    """
    Provide a ConfigManager instance with test values — no real API keys needed.

    FIX: original used lowercase keys (ollama_api_key) but ConfigManager
    stores .env keys in their original case (OLLAMA_API_KEY). Lowercase keys
    caused get_required('env.OLLAMA_API_KEY') to return None in tests.
    """
    from src.utils.config_loader import ConfigManager

    config = ConfigManager.__new__(ConfigManager)
    config.config_path = "configs/config.yaml"
    config._config = {
        "runtime": {"orchestration": "langchain"},
        # FIX: uppercase keys — match what dotenv_values() returns from .env files
        "env": {
            "OLLAMA_API_KEY": "test-key",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3.1",
            "OPENWEATHER_API_KEY": "test-weather-key",
            "OPENWEATHER_BASE_URL": "https://api.openweathermap.org/data/2.5",
        },
    }
    return config


@pytest.fixture
def mock_all_apis(mock_weather_api, mock_ollama_api, mock_web_search_api):
    """
    Combined fixture for integration tests that call multiple APIs.
    """
    return {
        "weather": mock_weather_api,
        "ollama": mock_ollama_api,
        "web_search": mock_web_search_api,
    }
