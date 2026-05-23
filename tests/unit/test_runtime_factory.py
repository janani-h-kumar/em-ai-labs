from unittest.mock import Mock

from src.runtimes.runtime_factory import RuntimeFactory


def test_runtime_factory_exists():
    factory = RuntimeFactory()
    assert factory is not None


def test_create_langchain_runtime():
    config = Mock()
    config.get.return_value = "langchain"

    runtime = RuntimeFactory.create_runtime(config)

    assert runtime is not None
