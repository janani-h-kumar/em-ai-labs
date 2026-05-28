from unittest.mock import patch

from src import main


def test_main_module_imports():
    assert main is not None


@patch("src.main.AgentManager")
def test_create_agent_manager(mock_agent_manager):
    agent_manager = main.AgentManager("config.yaml")

    assert agent_manager is not None
