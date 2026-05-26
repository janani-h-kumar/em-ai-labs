# tests/tools/test_tool_registry.py

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from src.tools.base_tool import BaseTool
from src.tools.tool_registry import ToolRegistry


@pytest.fixture
def mock_config():
    config = MagicMock()

    config_values = {
        "llm.provider": "ollama",
        "llm.model": "llama3",
        "llm.base_url": "http://localhost:11434",
    }

    config.get.side_effect = lambda key, default=None: config_values.get(key, default)

    return config


# -------------------------------------------------------------------
# Fake Test Schema
# -------------------------------------------------------------------


class FakeInput(BaseModel):
    query: str


# -------------------------------------------------------------------
# Fake Valid Tool
# -------------------------------------------------------------------


class FakeTool(BaseTool):
    name = "fake_tool"

    description = "Fake test tool"

    args_schema = FakeInput

    def _run(self, *args, **kwargs):
        return "success"


# -------------------------------------------------------------------
# Fake Broken Tool
# -------------------------------------------------------------------


class BrokenTool(BaseTool):
    name = "broken_tool"

    description = "Broken tool"

    args_schema = FakeInput

    def __init__(self, mock_config):
        raise RuntimeError("boom")

    def _run(self, *args, **kwargs):
        return "never"


# -------------------------------------------------------------------
# Tests
# -------------------------------------------------------------------


def test_registry_starts_empty(mock_config):
    """
    Registry should initialize with no tools loaded.
    """

    registry = ToolRegistry(mock_config)

    assert registry._tool_instances == {}


def test_registers_valid_tool(mock_config):
    """
    Registry should store valid BaseTool subclasses.
    """

    registry = ToolRegistry(mock_config)

    tool = FakeTool(mock_config)

    registry._tool_instances[tool.name] = tool

    assert "fake_tool" in registry._tool_instances


def test_get_tool_returns_registered_tool(mock_config):
    """
    Registry should return the correct tool instance by name.
    """

    registry = ToolRegistry(mock_config)

    tool = FakeTool(mock_config)

    registry._tool_instances[tool.name] = tool

    result = registry.get_tool("fake_tool")

    assert result == tool


def test_get_tool_raises_for_missing_tool(mock_config):
    """
    Registry should raise KeyError for unknown tools.
    """

    registry = ToolRegistry(mock_config)

    with pytest.raises(KeyError):
        registry.get_tool("missing_tool")


def test_get_langchain_tools_returns_tool_instances(
    mock_config,
):
    """
    Registry should convert BaseTool instances into LangChain tools.
    """

    registry = ToolRegistry(mock_config)

    tool = FakeTool(mock_config)

    registry._tool_instances[tool.name] = tool

    tools = registry.get_langchain_tools()

    assert len(tools) == 1

    assert tools[0].name == "fake_tool"


def test_tool_receives_config_manager(mock_config):
    """
    Tools should receive injected ConfigManager dependency.
    """

    tool = FakeTool(mock_config)

    assert tool.config_manager is mock_config


def test_broken_tool_initialization_is_isolated(
    mock_config,
):
    """
    A broken tool should fail independently and not impact registry state.
    """

    registry = ToolRegistry(mock_config)

    with pytest.raises(RuntimeError):
        BrokenTool(mock_config)

    assert "broken_tool" not in registry._tool_instances
