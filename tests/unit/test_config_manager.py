import pytest

from src.utils.config_loader import (
    ConfigManager,
    ConfigError,
    ConfigValidationError,
)


# -------------------------------------------------
# Helper: create valid base config
# -------------------------------------------------
VALID_CONFIG = """
runtime:
  orchestration: langchain

env:
  OLLAMA_API_KEY: test-key
  OLLAMA_BASE_URL: http://localhost:11434
  OPENWEATHER_API_KEY: test-key
  OPENWEATHER_BASE_URL: http://api.weather.com
"""


# -------------------------------------------------
# 1. Missing config file → SHOULD RAISE
# -------------------------------------------------
def test_missing_config_file_raises(tmp_path):
    missing_path = tmp_path / "does_not_exist.yaml"

    with pytest.raises(ConfigError):
        ConfigManager(str(missing_path))


# -------------------------------------------------
# 2. Invalid YAML → SHOULD RAISE
# -------------------------------------------------
def test_invalid_yaml_raises(tmp_path):
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("""
    runtime:
      orchestration: langchain
        broken_indent: true
    """)

    with pytest.raises(ConfigError):
        ConfigManager(str(bad_file))


# -------------------------------------------------
# 3. Valid config loads correctly
# -------------------------------------------------
def test_valid_config_loads(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text(VALID_CONFIG)

    cfg = ConfigManager(str(file))

    assert cfg.get("runtime.orchestration") == "langchain"
    assert "env" in cfg.get_all()


# -------------------------------------------------
# 4. get() returns default when missing key
# -------------------------------------------------
def test_get_returns_default(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text(VALID_CONFIG)

    cfg = ConfigManager(str(file))

    assert cfg.get("runtime.missing", "default") == "default"


# -------------------------------------------------
# 5. get_required() raises when missing
# -------------------------------------------------
def test_get_required_raises(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text(VALID_CONFIG)

    cfg = ConfigManager(str(file))

    with pytest.raises(ConfigValidationError):
        cfg.get_required("runtime.missing")


# -------------------------------------------------
# 6. validate_startup passes for valid config
# -------------------------------------------------
def test_validate_startup_passes(tmp_path, monkeypatch):
    file = tmp_path / "config.yaml"

    file.write_text("""
runtime:
  orchestration: langchain
""")

    # IMPORTANT: set real env vars (this is how your system works)
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
    monkeypatch.setenv("OPENWEATHER_BASE_URL", "http://api.weather.com")

    cfg = ConfigManager(str(file))

    # should NOT raise
    cfg.validate_startup()


# -------------------------------------------------
# 7. validate_startup fails when required keys missing
# -------------------------------------------------
def test_validate_startup_fails(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text("""
runtime:
  orchestration: langchain
""")

    cfg = ConfigManager(str(file))

    with pytest.raises(ConfigValidationError):
        cfg.validate_startup()


# -------------------------------------------------
# 8. set() modifies in-memory config
# -------------------------------------------------
def test_set_updates_config(tmp_path):
    file = tmp_path / "config.yaml"
    file.write_text(VALID_CONFIG)

    cfg = ConfigManager(str(file))

    cfg.set("runtime.orchestration", "custom")

    assert cfg.get("runtime.orchestration") == "custom"