import pytest
from unittest.mock import MagicMock

from src.providers.ollama_provider import (
    OllamaClient,
    OllamaError,
)


class MockConfig:
    """Mock config object for testing."""

    def get(self, key, default=None):
        values = {
            "env.OLLAMA_BASE_URL": "http://localhost:11434",
            "env.OLLAMA_MODEL": "qwen2.5",
            "env.OLLAMA_API_KEY": None,
        }
        return values.get(key, default)


@pytest.fixture
def mock_config():
    return MockConfig()


@pytest.fixture
def client(monkeypatch, mock_config):
    """
    Prevent real HTTP/OpenAI calls by mocking validation methods.
    """
    monkeypatch.setattr(OllamaClient, "_validate_connection", lambda self: None)
    monkeypatch.setattr(OllamaClient, "_validate_model_exists", lambda self: None)
    return OllamaClient(mock_config)


class TestOllamaClient:

    def test_chat_completion_success(self, monkeypatch, client):
        """Should return parsed response successfully."""

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="AI is artificial intelligence."))
        ]

        monkeypatch.setattr(
            client.client.chat.completions,
            "create",
            lambda **kwargs: mock_response
        )

        response = client.chat_completion("What is AI?")

        assert response == "AI is artificial intelligence."

    def test_string_prompt_converted_to_messages(self, monkeypatch, client):
        """Should convert string prompts into message format."""

        captured = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            mock = MagicMock()
            mock.choices = [
                MagicMock(message=MagicMock(content="ok"))
            ]
            return mock

        monkeypatch.setattr(
            client.client.chat.completions,
            "create",
            fake_create
        )

        client.chat_completion("What is AI?")

        assert captured["messages"] == [
            {"role": "user", "content": "What is AI?"}
        ]

    def test_multi_turn_conversation_passed_correctly(self, monkeypatch, client):
        """Should preserve multi-turn conversation structure."""

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]

        captured = {}

        def fake_create(**kwargs):
            captured.update(kwargs)
            mock = MagicMock()
            mock.choices = [
                MagicMock(message=MagicMock(content="response"))
            ]
            return mock

        monkeypatch.setattr(
            client.client.chat.completions,
            "create",
            fake_create
        )

        client.chat_completion(messages)

        assert captured["messages"] == messages

    def test_connection_error_raises_custom_exception(self, monkeypatch, client):
        """Should convert connection failures into domain exception."""

        def raise_error(**kwargs):
            raise Exception("Connection failed")

        monkeypatch.setattr(
            client.client.chat.completions,
            "create",
            raise_error
        )

        with pytest.raises(OllamaError):
            client.chat_completion("hello")

    def test_empty_response_raises_error(self, monkeypatch, client):
        """Should raise error for empty response."""

        mock = MagicMock()
        mock.choices = []

        monkeypatch.setattr(
            client.client.chat.completions,
            "create",
            lambda **kwargs: mock
        )

        with pytest.raises(OllamaError):
            client.chat_completion("hello")

    def test_none_response_raises_error(self, monkeypatch, client):
        """Should raise error for None response."""

        monkeypatch.setattr(
            client.client.chat.completions,
            "create",
            lambda **kwargs: None
        )

        with pytest.raises(OllamaError):
            client.chat_completion("hello")

    def test_model_name_loaded_from_config(self, mock_config):
        """Should initialize client with configured model."""

        client = OllamaClient(mock_config)
        assert client.model_name == "qwen2.5"