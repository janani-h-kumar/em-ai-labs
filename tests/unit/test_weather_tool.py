from unittest.mock import MagicMock, patch

import pytest

from src.tools.weather_tool import (
    CityNotFoundError,
    WeatherAPIError,
    WeatherClient,
    WeatherConfigError,
    WeatherTool,
)


# -------------------------
# Fixtures
# -------------------------
@pytest.fixture
def mock_config():
    config = MagicMock()

    values = {
        "env.OPENWEATHER_API_KEY": "test-key",
        "env.OPENWEATHER_BASE_URL": "http://fake-api.com",
    }

    config.get.side_effect = lambda k, default=None: values.get(k, default)
    config.get_required.side_effect = lambda k: values[k]

    return config


# -------------------------
# WeatherClient init success
# -------------------------
@patch("src.tools.weather_tool.requests.head")
def test_weather_client_init_success(mock_head, mock_config):
    mock_head.return_value.status_code = 200

    client = WeatherClient(mock_config)

    assert client.api_key == "test-key"
    assert client.base_url == "http://fake-api.com"


# -------------------------
# Missing base_url -> WeatherConfigError
# -------------------------
def test_weather_client_missing_base_url(mock_config):
    mock_config.get.side_effect = lambda k, default=None: None
    mock_config.get_required.side_effect = lambda k: "test-key"

    with pytest.raises(WeatherConfigError):
        WeatherClient(mock_config)


# -------------------------
# Invalid city input
# -------------------------
@patch("src.tools.weather_tool.requests.head")
def test_get_temperature_invalid_city(mock_head, mock_config):
    mock_head.return_value.status_code = 200

    client = WeatherClient(mock_config)

    with pytest.raises(ValueError):
        client.get_temperature("")


# -------------------------
# Successful weather fetch (200)
# -------------------------
@patch("src.tools.weather_tool.requests.get")
@patch("src.tools.weather_tool.requests.head")
def test_fetch_weather_success(mock_head, mock_get, mock_config):
    mock_head.return_value.status_code = 200

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "name": "Seattle",
        "sys": {"country": "US"},
        "main": {
            "temp": 72,
            "feels_like": 70,
            "humidity": 50,
            "pressure": 1010,
        },
        "weather": [{"main": "Clouds", "description": "broken clouds"}],
    }
    mock_get.return_value = mock_resp

    client = WeatherClient(mock_config)

    result = client.get_temperature("Seattle")

    assert result["city"] == "Seattle"
    assert result["temperature"] == 72
    assert result["condition"] == "Clouds"


# -------------------------
# 404 -> CityNotFoundError
# -------------------------
@patch("src.tools.weather_tool.requests.get")
@patch("src.tools.weather_tool.requests.head")
def test_city_not_found(mock_head, mock_get, mock_config):
    mock_head.return_value.status_code = 200

    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp

    client = WeatherClient(mock_config)

    with pytest.raises(CityNotFoundError):
        client.get_temperature("NowhereCity")


# -------------------------
# 401 -> WeatherAPIError
# -------------------------
@patch("src.tools.weather_tool.requests.get")
@patch("src.tools.weather_tool.requests.head")
def test_invalid_api_key(mock_head, mock_get, mock_config):
    mock_head.return_value.status_code = 200

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_get.return_value = mock_resp

    client = WeatherClient(mock_config)

    with pytest.raises(WeatherAPIError):
        client.get_temperature("Seattle")


# -------------------------
# WeatherTool _run success
# -------------------------
def test_weather_tool_run_success(mock_config):
    tool = WeatherTool.__new__(WeatherTool)
    tool.client = MagicMock()

    tool.client.get_temperature.return_value = {
        "city": "Seattle",
        "temperature": 72,
    }

    result = tool._run(city="Seattle")

    assert "Seattle" in result


# -------------------------
# WeatherTool missing city
# -------------------------
def test_weather_tool_missing_city(mock_config):
    tool = WeatherTool.__new__(WeatherTool)
    tool.client = MagicMock()

    with pytest.raises(ValueError):
        tool._run()
