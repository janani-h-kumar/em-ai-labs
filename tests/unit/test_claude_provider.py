import os
from unittest.mock import MagicMock

import pytest

from src.providers.claude_provider import ClaudeProvider  # Adjust import path if needed

# Define the skip condition based on the environment variable
HAS_API_KEY = "ANTHROPIC_API_KEY" in os.environ

@pytest.mark.skipif(not HAS_API_KEY, reason="Skipping integration test: ANTHROPIC_API_KEY is not set")
def test_claude_provider_health_check_integration():
    # Arrange: Create a real configuration manager that pulls from the environment
    # Alternatively, you can use a Mock if your config_manager usually handles it,
    # but since this is gated by the actual environment key, we mimic the integration setup.
    config_manager = MagicMock()
    config_manager.get.side_effect = lambda key, default=None: {
        "env.anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY"),
        "claude.model": "claude-haiku-4-5-20251001",
        "claude.max_tokens": 1000
    }.get(key, default)

    provider = ClaudeProvider(config_manager)

    # Act
    result = provider.health_check()

    # Assert
    assert result is True, "Health check failed despite having a valid API key"
