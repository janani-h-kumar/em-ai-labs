"""
Enterprise Pytest test suite for WeatherAgent.
"""

import time
from unittest.mock import Mock

import pytest

from src.agents.weather_agent import WeatherAgent, WeatherAgentExecutionError
from src.middleware.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)
from src.middleware.retry import retry_with_backoff
from src.tools.weather_tool import CityNotFoundError
from src.utils.config_loader import ConfigValidationError

# ---------------------------------------------------------------------------
# Shared Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent(config_for_testing):
    """
    Fully initialized WeatherAgent fixture using dependency injection.
    """
    return WeatherAgent(
        config_manager=config_for_testing,
        base_llm_provider=Mock(),
        weather_client=Mock(),
    )


# ---------------------------------------------------------------------------
# WeatherAgent initialization tests
# ---------------------------------------------------------------------------


class TestWeatherAgentInitialization:
    def test_agent_initializes_successfully(self, config_for_testing):
        mock_llm = Mock()
        mock_weather = Mock()

        agent = WeatherAgent(
            config_manager=config_for_testing,
            base_llm_provider=mock_llm,
            weather_client=mock_weather,
        )

        assert agent.is_initialized() is True

        assert (
            agent.config_manager.get("runtime.orchestration")
            == "langchain"
        )


# ---------------------------------------------------------------------------
# extract_city tests
# ---------------------------------------------------------------------------


class TestExtractCity:
    def test_extracts_simple_city(self, agent):
        assert agent.extract_city("Weather in London") == "London"

    def test_extracts_multi_word_city(self, agent):
        city = agent.extract_city(
            "What is the weather in New York today?"
        )

        assert city == "New York"

    def test_does_not_return_filler_words(self, agent):
        city = agent.extract_city("what's the weather today?")

        assert city == "New York"

    def test_empty_string_returns_default(self, agent):
        assert agent.extract_city("") == "New York"

    def test_none_like_empty_returns_default(self, agent):
        assert agent.extract_city("   ") == "New York"

    def test_titled_city_extracted(self, agent):
        result = agent.extract_city("Is it raining in Paris?")

        assert result == "Paris"


# ---------------------------------------------------------------------------
# Weather summary tests
# ---------------------------------------------------------------------------


class TestWeatherSummary:
    def test_get_weather_summary_returns_string(
        self,
        config_for_testing,
    ):
        mock_wc = Mock()

        mock_wc.get_temperature.return_value = {
            "city": "London",
            "country": "GB",
            "temperature": 15.2,
            "feels_like": 14.8,
            "humidity": 72,
            "pressure": 1013,
            "condition": "Cloudy",
            "description": "overcast clouds",
            "units": "imperial",
        }

        mock_llm = Mock()

        mock_llm.chat_completion.return_value = (
            "London is cloudy and mild today!"
        )

        agent = WeatherAgent(
            config_manager=config_for_testing,
            base_llm_provider=mock_llm,
            weather_client=mock_wc,
        )

        result = agent.get_weather_summary("London")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_city_not_found_raises_execution_error(
        self,
        config_for_testing,
    ):
        mock_wc = Mock()

        mock_wc.get_temperature.side_effect = (
            CityNotFoundError("Fake City not found")
        )

        agent = WeatherAgent(
            config_manager=config_for_testing,
            base_llm_provider=Mock(),
            weather_client=mock_wc,
        )

        with pytest.raises(
            WeatherAgentExecutionError,
            match="City not found",
        ):
            agent.get_weather_summary("Fake City")

    def test_empty_city_raises_value_error(
        self,
        config_for_testing,
    ):
        agent = WeatherAgent(
            config_manager=config_for_testing,
            base_llm_provider=Mock(),
            weather_client=Mock(),
        )

        with pytest.raises(
            ValueError,
            match="non-empty",
        ):
            agent.get_weather_summary("")


# ---------------------------------------------------------------------------
# ConfigManager tests
# ---------------------------------------------------------------------------


class TestConfigManager:
    def test_get_existing_key(self, config_for_testing):
        assert (
            config_for_testing.get("runtime.orchestration")
            == "langchain"
        )

    def test_get_missing_key_returns_default(
        self,
        config_for_testing,
    ):
        assert (
            config_for_testing.get(
                "nonexistent.key",
                default="fallback",
            )
            == "fallback"
        )

    def test_get_required_raises_on_missing(
        self,
        config_for_testing,
    ):
        with pytest.raises(ConfigValidationError):
            config_for_testing.get_required(
                "env.DOES_NOT_EXIST"
            )

    def test_set_updates_value(self, config_for_testing):
        config_for_testing.set(
            "runtime.orchestration",
            "custom",
        )

        assert (
            config_for_testing.get("runtime.orchestration")
            == "custom"
        )

    def test_validate_startup_passes_with_full_config(
        self,
        config_for_testing,
    ):
        config_for_testing.validate_startup()

    def test_validate_startup_raises_on_missing_key(
        self,
        config_for_testing,
    ):
        config_for_testing._config["env"].pop(
            "OPENWEATHER_API_KEY",
            None,
        )

        with pytest.raises(ConfigValidationError):
            config_for_testing.validate_startup()


# ---------------------------------------------------------------------------
# CircuitBreaker tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def setup_method(self):
        self.cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            service_name="test-service",
        )

    def test_successful_call_passes_through(self):
        result = self.cb.call(lambda: "ok")

        assert result == "ok"

    def test_circuit_opens_after_threshold_failures(self):
        def always_fails():
            raise ConnectionError("boom")

        for _ in range(3):
            try:
                self.cb.call(always_fails)
            except ConnectionError:
                pass

        assert self.cb.state == CircuitState.OPEN

    def test_open_circuit_raises_circuit_breaker_open(self):
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = time.time()

        with pytest.raises(CircuitBreakerOpenError):
            self.cb.call(lambda: "should not run")

    def test_circuit_resets_after_successful_half_open(self):
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = time.time() - 9999

        self.cb.call(lambda: "ok")
        self.cb.call(lambda: "ok")

        assert self.cb.state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Retry middleware tests
# ---------------------------------------------------------------------------


class TestRetryWithBackoff:
    def test_succeeds_on_first_attempt(self):
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

        assert call_count == 1

    def test_raises_after_exhausting_retries(self):
        @retry_with_backoff(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ConnectionError,),
        )
        def always_fails():
            raise ConnectionError("always down")

        with pytest.raises(ConnectionError):
            always_fails()
