from unittest.mock import Mock

from src.runtimes.langchain_runtime import LangChainRuntime


def test_runtime_initializes():
    config = Mock()

    runtime = LangChainRuntime(config)

    assert runtime is not None


def test_runtime_has_config():
    config = Mock()

    runtime = LangChainRuntime(config)

    assert runtime.config_manager == config
