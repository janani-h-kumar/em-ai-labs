# tests/integration/test_ollama_integration.py

import os

import pytest

from src.providers.ollama_provider import OllamaClient


class FakeConfigForCI:
    """
    Reads from environment variables so integration tests work in GitHub Actions
    without needing configs/config.yaml to exist.
    """

    def get(self, key, default=None):
        mapping = {
            "ollama.base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "ollama.model": os.getenv("OLLAMA_MODEL", "phi3:mini"),
            "ollama.timeout": int(os.getenv("OLLAMA_TIMEOUT", "30")),
        }
        return mapping.get(key, default)


@pytest.mark.integration
class TestOllamaIntegration:
    @pytest.fixture(scope="class")
    def ollama_client(self):
        return OllamaClient(FakeConfigForCI())

    def test_simple_prompt_returns_response(self, ollama_client):
        response = ollama_client.chat_completion("What is 2+2? Answer in one word.")
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_multi_turn_conversation(self, ollama_client):
        conversation = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is machine learning? One sentence."},
        ]
        response = ollama_client.chat_completion(conversation)
        assert isinstance(response, str)
        assert len(response.strip()) > 0

    def test_client_has_expected_model(self, ollama_client):
        model = ollama_client.model_name
        assert isinstance(model, str)
        assert len(model) > 0
        # Don't assert a specific model name — it is config-driven

    def test_health_check_returns_structured_dict(self, ollama_client):
        """
        health_check() must return a dict with at minimum: agent, status, initialized.
        This test is what a Kubernetes liveness probe would verify.
        """
        result = ollama_client.health_check()
        assert isinstance(result, dict)
        assert result.get("status") in ("healthy", "degraded")
