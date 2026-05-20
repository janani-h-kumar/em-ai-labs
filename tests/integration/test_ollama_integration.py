import pytest

from src.providers.ollama_provider import (
    ConfigManager,
    OllamaClient,
)


@pytest.mark.integration
class TestOllamaIntegration:

    @pytest.fixture(scope="class")
    def config_manager(self):
        return ConfigManager("configs/config.yaml")

    @pytest.fixture(scope="class")
    def ollama_client(self, config_manager):
        return OllamaClient(config_manager)

    def test_simple_prompt_returns_response(self, ollama_client):
        response = ollama_client.chat_completion(
            "What is AI?"
        )

        assert response is not None
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_multi_turn_conversation(self, ollama_client):

        conversation = [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "What is machine learning?"
            }
        ]

        response = ollama_client.chat_completion(conversation)

        assert response is not None
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_client_has_expected_model(self, ollama_client):
        assert ollama_client.model_name == "qwen2.5"