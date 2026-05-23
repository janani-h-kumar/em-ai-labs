from src.runtimes.langchain_runtime import LangChainRuntime
from src.runtimes.runtime_factory import RuntimeFactory


def test_create_langchain_runtime(mock_config):
    runtime = RuntimeFactory.create(
        runtime_type="langchain",
        config_manager=mock_config,
        tools=[],
    )

    assert isinstance(runtime, LangChainRuntime)
