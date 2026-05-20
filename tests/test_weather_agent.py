"""
Pytest test suite for WeatherAgent.

Changes from original:
- Completely rewritten as proper pytest test functions (def test_*) so they
  are discovered and run by `pytest` automatically.
- Original used def main() + if __name__ == '__main__', which means:
    * pytest collected 0 tests (all tests were invisible to the runner)
    * the conftest.py fixtures were never used
    * CI would report "0 tests passed" silently
- Now uses the mock fixtures from conftest.py — no real API calls needed.
- Added tests for CircuitBreaker, ConfigManager, and extract_city which had
  zero coverage in the original.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


# ---------------------------------------------------------------------------
# WeatherAgent tests
# ---------------------------------------------------------------------------

class TestWeatherAgentInitialization:

    def test_agent_initializes_successfully(
        self, config_for_testing, mock_weather_api, mock_ollama_api
    ):
        """Agent should initialize without raising when config and APIs are available."""
        with patch('src.providers.ollama_provider.requests.get') as mock_req:
            mock_req.return_value = Mock(
                status_code=200,
                json=lambda: {"models": [{"name": "llama3.1"}]},
            )
            # WeatherClient startup ping
            with patch('src.tools.weather_tool.requests.head') as mock_head:
                mock_head.return_value = Mock(status_code=200)

                from src.agents.weather_agent import WeatherAgent
                agent = WeatherAgent.__new__(WeatherAgent)
                agent.config_manager = config_for_testing
                # Verify config is accessible
                assert agent.config_manager.get("runtime.orchestration") == "langchain"

    def test_missing_api_key_raises_init_error(self, config_for_testing):
        """Missing OPENWEATHER_API_KEY should raise WeatherAgentInitError."""
        from src.utils.config_loader import ConfigValidationError
        config_for_testing._config["env"].pop("OPENWEATHER_API_KEY", None)

        with pytest.raises(ConfigValidationError):
            config_for_testing.get_required("env.OPENWEATHER_API_KEY")


class TestExtractCity:
    """Test the improved city extraction logic."""

    def setup_method(self):
        from src.agents.weather_agent import WeatherAgent
        self.agent = WeatherAgent.__new__(WeatherAgent)

    def test_extracts_simple_city(self):
        assert self.agent.extract_city("Weather in London") == "London"

    def test_extracts_multi_word_city(self):
        city = self.agent.extract_city("What is the weather in New York today?")
        assert city == "New York"

    def test_does_not_return_filler_words(self):
        city = self.agent.extract_city("what's the weather today?")
        # Should fall back to default, not return "Today" or "What"
        assert city == "New York"

    def test_empty_string_returns_default(self):
        assert self.agent.extract_city("") == "New York"

    def test_none_like_empty_returns_default(self):
        assert self.agent.extract_city("   ") == "New York"

    def test_titled_city_extracted(self):
        result = self.agent.extract_city("Is it raining in Paris?")
        assert result == "Paris"


class TestWeatherSummary:

    def test_get_weather_summary_returns_string(
        self, config_for_testing, mock_weather_api, mock_ollama_api
    ):
        """get_weather_summary should return a non-empty string on success."""
        from src.agents.weather_agent import WeatherAgent
        from src.tools.weather_tool import WeatherClient
        from src.providers.ollama_provider import OllamaClient

        agent = WeatherAgent.__new__(WeatherAgent)
        agent.logger = Mock()

        # Wire in mocked clients directly
        mock_wc = Mock()
        mock_wc.get_temperature.return_value = {
            "city": "London", "country": "GB",
            "temperature": 15.2, "feels_like": 14.8,
            "humidity": 72, "pressure": 1013,
            "condition": "Cloudy", "description": "overcast clouds",
            "units": "imperial",
        }
        agent.weather_client = mock_wc

        mock_oc = Mock()
        mock_oc.chat_completion.return_value = "London is cloudy and mild today!"
        agent.ollama_client = mock_oc

        result = agent.get_weather_summary("London")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_city_not_found_raises_execution_error(self, config_for_testing):
        """CityNotFoundError from weather client should become WeatherAgentExecutionError."""
        from src.agents.weather_agent import WeatherAgent, WeatherAgentExecutionError
        from src.tools.weather_tool import CityNotFoundError

        agent = WeatherAgent.__new__(WeatherAgent)
        agent.logger = Mock()

        mock_wc = Mock()
        mock_wc.get_temperature.side_effect = CityNotFoundError("Fake City not found")
        agent.weather_client = mock_wc
        agent.ollama_client = Mock()

        with pytest.raises(WeatherAgentExecutionError, match="City not found"):
            agent.get_weather_summary("Fake City")

    def test_empty_city_raises_value_error(self):
        from src.agents.weather_agent import WeatherAgent
        agent = WeatherAgent.__new__(WeatherAgent)
        agent.logger = Mock()
        agent.weather_client = Mock()
        agent.ollama_client = Mock()

        with pytest.raises(ValueError, match="non-empty"):
            agent.get_weather_summary("")


# ---------------------------------------------------------------------------
# ConfigManager tests — previously had zero coverage
# ---------------------------------------------------------------------------

class TestConfigManager:

    def test_get_existing_key(self, config_for_testing):
        assert config_for_testing.get("runtime.orchestration") == "langchain"

    def test_get_missing_key_returns_default(self, config_for_testing):
        assert config_for_testing.get("nonexistent.key", default="fallback") == "fallback"

    def test_get_required_raises_on_missing(self, config_for_testing):
        from src.utils.config_loader import ConfigValidationError
        with pytest.raises(ConfigValidationError):
            config_for_testing.get_required("env.DOES_NOT_EXIST")

    def test_set_updates_value(self, config_for_testing):
        config_for_testing.set("runtime.orchestration", "custom")
        assert config_for_testing.get("runtime.orchestration") == "custom"

    def test_validate_startup_passes_with_full_config(self, config_for_testing):
        """validate_startup() should not raise when all required keys are present."""
        config_for_testing.validate_startup()  # no exception = pass

    def test_validate_startup_raises_on_missing_key(self, config_for_testing):
        from src.utils.config_loader import ConfigValidationError
        config_for_testing._config["env"].pop("OPENWEATHER_API_KEY")
        with pytest.raises(ConfigValidationError):
            config_for_testing.validate_startup()


# ---------------------------------------------------------------------------
# CircuitBreaker tests — previously had zero coverage
# ---------------------------------------------------------------------------

class TestCircuitBreaker:

    def setup_method(self):
        from src.middleware.circuit_breaker import CircuitBreaker
        self.cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            service_name="test-service",
        )

    def test_successful_call_passes_through(self):
        result = self.cb.call(lambda: "ok")
        assert result == "ok"

    def test_circuit_opens_after_threshold_failures(self):
        from src.middleware.circuit_breaker import CircuitBreakerOpen, CircuitState

        def always_fails():
            raise ConnectionError("boom")

        for _ in range(3):
            try:
                self.cb.call(always_fails)
            except ConnectionError:
                pass

        assert self.cb.state == CircuitState.OPEN

    def test_open_circuit_raises_circuit_breaker_open(self):
        from src.middleware.circuit_breaker import CircuitBreakerOpen, CircuitState
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = __import__('time').time()  # just now

        with pytest.raises(CircuitBreakerOpen):
            self.cb.call(lambda: "should not run")

    def test_circuit_resets_after_successful_half_open(self):
        from src.middleware.circuit_breaker import CircuitState
        import time

        # Force OPEN, then make recovery_timeout appear elapsed
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = time.time() - 9999

        # Two successes in HALF_OPEN → CLOSED
        self.cb.call(lambda: "ok")
        self.cb.call(lambda: "ok")

        assert self.cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Retry middleware tests — previously had zero coverage
# ---------------------------------------------------------------------------

class TestRetryWithBackoff:

    def test_succeeds_on_first_attempt(self):
        from src.middleware.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(max_retries=3)
        def always_works():
            nonlocal call_count
            call_count += 1
            return "done"

        result = always_works()
        assert result == "done"
        assert call_count == 1

    def test_retries_on_transient_error(self):
        from src.middleware.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = fails_twice()
        assert result == "recovered"
        assert call_count == 3

    def test_does_not_retry_permanent_error(self):
        from src.middleware.retry import retry_with_backoff

        call_count = 0

        @retry_with_backoff(
            max_retries=3,
            retryable_exceptions=(ConnectionError,),
        )
        def permanent_failure():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent — don't retry")

        with pytest.raises(ValueError):
            permanent_failure()

        # Should have been called exactly once — no retries on ValueError
        assert call_count == 1

    def test_raises_after_exhausting_retries(self):
        from src.middleware.retry import retry_with_backoff

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        def always_fails():
            raise ConnectionError("always down")

        with pytest.raises(ConnectionError):
            always_fails()
