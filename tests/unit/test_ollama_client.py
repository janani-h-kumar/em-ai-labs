import pytest

from src.providers.ollama_provider import (
    OllamaClient,
    OllamaError,
    OllamaConnectionError,
)


class MockConfig:
    """Mock config object for testing."""

    def get(self, key, default=None):

        values = {
            "ollama.host": "http://localhost:11434",
            "ollama.model": "qwen2.5",
            "ollama.timeout": 30,
        }

        return values.get(key, default)


@pytest.fixture
def mock_config():
    return MockConfig()


class TestOllamaClient:
    """Unit tests for OllamaClient."""

    def test_chat_completion_success(self, mocker, mock_config):
        """Should return parsed response successfully."""

        mock_chat = mocker.patch(
            "src.providers.ollama_provider.Client.chat"
        )

        mock_chat.return_value = {
            "message": {
                "content": "AI is artificial intelligence."
            }
        }

        client = OllamaClient(mock_config)

        response = client.chat_completion("What is AI?")

        assert response == "AI is artificial intelligence."

    def test_string_prompt_converted_to_messages(
        self,
        mocker,
        mock_config
    ):
        """Should convert string prompts into Ollama message format."""

        mock_chat = mocker.patch(
            "src.providers.ollama_provider.Client.chat"
        )

        mock_chat.return_value = {
            "message": {
                "content": "hello"
            }
        }

        client = OllamaClient(mock_config)

        client.chat_completion("What is AI?")

        mock_chat.assert_called_once()

        call_kwargs = mock_chat.call_args.kwargs

        assert call_kwargs["messages"] == [
            {
                "role": "user",
                "content": "What is AI?"
            }
        ]

    def test_multi_turn_conversation_passed_correctly(
        self,
        mocker,
        mock_config
    ):
        """Should preserve multi-turn conversation structure."""

        mock_chat = mocker.patch(
            "src.providers.ollama_provider.Client.chat"
        )

        mock_chat.return_value = {
            "message": {
                "content": "response"
            }
        }

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]

        client = OllamaClient(mock_config)

        client.chat_completion(messages)

        call_kwargs = mock_chat.call_args.kwargs

        assert call_kwargs["messages"] == messages

    def test_connection_error_raises_custom_exception(
        self,
        mocker,
        mock_config
    ):
        """Should convert connection failures into domain exception."""

        mock_chat = mocker.patch(
            "src.providers.ollama_provider.Client.chat"
        )

        mock_chat.side_effect = ConnectionError("Connection failed")

        client = OllamaClient(mock_config)

        with pytest.raises(OllamaConnectionError):
            client.chat_completion("hello")

    def test_empty_response_raises_error(
        self,
        mocker,
        mock_config
    ):
        """Should raise OllamaError for malformed responses."""

        mock_chat = mocker.patch(
            "src.providers.ollama_provider.Client.chat"
        )

        mock_chat.return_value = {}

        client = OllamaClient(mock_config)

        with pytest.raises(OllamaError):
            client.chat_completion("hello")

    def test_none_response_raises_error(
        self,
        mocker,
        mock_config
    ):
        """Should raise OllamaError for null responses."""

        mock_chat = mocker.patch(
            "src.providers.ollama_provider.Client.chat"
        )

        mock_chat.return_value = None

        client = OllamaClient(mock_config)

        with pytest.raises(OllamaError):
            client.chat_completion("hello")

    def test_model_name_loaded_from_config(self, mock_config):
        """Should initialize client with configured model."""

        client = OllamaClient(mock_config)

        assert client.model_name == "qwen2.5"