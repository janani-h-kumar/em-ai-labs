import pytest

from src.providers.ollama_provider import (
    ConfigManager,
    ConfigError,
)


class TestConfigManager:
    """Unit tests for ConfigManager."""

    def test_load_valid_config(self, tmp_path):
        """Should load valid YAML config successfully."""

        config_file = tmp_path / "config.yaml"

        config_file.write_text("""
ollama:
  host: http://localhost:11434
  model: qwen2.5
""")

        config = ConfigManager(str(config_file))

        assert config.get("ollama.host") == "http://localhost:11434"
        assert config.get("ollama.model") == "qwen2.5"

    def test_missing_config_file_raises_error(self):
        """Should raise ConfigError for missing config file."""

        with pytest.raises(ConfigError):
            ConfigManager("does_not_exist.yaml")

    def test_invalid_yaml_raises_error(self, tmp_path):
        """Should raise ConfigError for malformed YAML."""

        config_file = tmp_path / "bad_config.yaml"

        config_file.write_text("""
ollama:
  model: qwen2.5
    invalid_indent
""")

        with pytest.raises(ConfigError):
            ConfigManager(str(config_file))

    def test_missing_key_returns_default(self, tmp_path):
        """Should return default value for missing keys."""

        config_file = tmp_path / "config.yaml"

        config_file.write_text("""
ollama:
  model: qwen2.5
""")

        config = ConfigManager(str(config_file))

        assert config.get("missing.key", "default") == "default"

    def test_missing_required_key_raises(self, tmp_path):
        """Should fail validation if required keys are missing."""

        config_file = tmp_path / "config.yaml"

        config_file.write_text("""
ollama:
  host: http://localhost:11434
""")

        with pytest.raises(ConfigError):
            ConfigManager(str(config_file))

    def test_environment_variable_substitution(self, tmp_path, monkeypatch):
        """Should substitute environment variables correctly."""

        monkeypatch.setenv("OLLAMA_MODEL", "llama3")

        config_file = tmp_path / "config.yaml"

        config_file.write_text("""
ollama:
  model: ${OLLAMA_MODEL}
""")

        config = ConfigManager(str(config_file))

        assert config.get("ollama.model") == "llama3"