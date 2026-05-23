from unittest.mock import Mock, patch

from src import main


def test_main_module_imports():
    assert main is not None


@patch("src.main.ConfigManager")
def test_create_config(mock_config):
    config = main.ConfigManager("config.yaml")

    assert config is not None


@patch("src.main.RuntimeFactory")
def test_runtime_factory_called(mock_factory):
    config = Mock()

    mock_factory.create_runtime.return_value = Mock()

    runtime = mock_factory.create_runtime(config)

    assert runtime is not None
