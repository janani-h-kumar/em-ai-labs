# GitHub Copilot Instructions — em-ai-labs

This file tells GitHub Copilot (and any AI coding assistant) how this repo is structured,
what patterns to follow, and what to avoid. Keep it updated as the harness evolves.

---

## Project purpose

An enterprise-grade AI agent harness built in Python. The goal is loosely coupled, observable,
testable agents that can be orchestrated to solve multi-step goals. Not a LangChain wrapper —
we own the orchestration logic intentionally.

---

## Language & runtime

- Python 3.11+ (use `match` statements, `str | None` union syntax, `tomllib`, etc.)
- No async yet — synchronous only until Phase 4 (then `asyncio`)
- Type hints required on all public methods and class attributes
- Docstrings required on all public classes and methods (Google style)

---

## Directory layout — what goes where

```
src/providers/    ← LLM clients only. ConfigManager lives here too (will move to src/config/ in Phase 2).
src/tools/        ← External API clients. One file per API. No LLM calls here.
src/agents/       ← Orchestration of tools + LLM. Business logic lives here.
src/main.py       ← CLI entry point only. No business logic.
tests/unit/       ← Fast tests. No network. Mock everything external.
tests/integration/← Slow tests. Real services. Mark with @pytest.mark.integration.
configs/          ← YAML config and .env. Never import from here in src/.
docs/             ← ARCHITECTURE.md, AGENTS.md, ADRs. Keep updated.
```

---

## Patterns Copilot MUST follow

### 1. Dependency injection — never instantiate providers inside agents

```python
# ✅ CORRECT — provider injected from outside
class WeatherAgent:
    def __init__(self, provider: BaseLLMProvider, config_manager: ConfigManager):
        self.provider = provider

# ❌ WRONG — agent creates its own provider
class WeatherAgent:
    def __init__(self):
        self.client = OllamaClient(ConfigManager("configs/config.yaml"))
```

### 2. Abstract base classes — use ABC, not duck typing

```python
# ✅ CORRECT
from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    @abstractmethod
    def chat_completion(self, messages: list[dict] | str) -> str: ...

# ❌ WRONG — no enforcement, Copilot will suggest this but don't accept it
class BaseLLMProvider:
    def chat_completion(self, messages):
        raise NotImplementedError
```

### 3. Module-scoped logger — never root logger, never print()

```python
# ✅ CORRECT — at the top of every module
import logging
logger = logging.getLogger(__name__)

# ❌ WRONG
import logging
logging.basicConfig(level=logging.DEBUG)   # never in library code
print("fetching weather...")               # never in production code
```

### 4. Structured logging with key=value pairs

```python
# ✅ CORRECT
logger.info("WeatherAgent.get_summary city=%s units=%s", city, units)
logger.error("WeatherTool failed city=%s error=%s", city, e, exc_info=True)

# ❌ WRONG — f-strings in log calls (eager evaluation, not lazy)
logger.info(f"Getting weather for {city}")
```

### 5. Custom exceptions — never raise bare Exception

```python
# ✅ CORRECT
class WeatherAgentExecutionError(WeatherAgentError):
    """Raised when the agent fails to produce a summary."""
    pass

raise WeatherAgentExecutionError(f"Failed to get summary for city={city}: {e}") from e

# ❌ WRONG
raise Exception("something went wrong")
raise RuntimeError(str(e))
```

### 6. Never catch bare Exception without re-raising or logging

```python
# ✅ CORRECT
try:
    data = self.weather_tool.get_temperature(city)
except WeatherAPIError as e:
    logger.error("WeatherTool failed city=%s error=%s", city, e, exc_info=True)
    raise WeatherAgentExecutionError(f"Failed for city={city}") from e

# ❌ WRONG — silently swallows errors
try:
    data = self.weather_tool.get_temperature(city)
except Exception:
    pass
```

### 7. Return structured results from tools — never raw dicts from APIs

```python
# ✅ CORRECT — tool normalises the API response
def get_temperature(self, city: str, units: str = "imperial") -> dict:
    """Returns: {city, temperature, condition, humidity, pressure, wind_speed}"""
    raw = self._api_call(city, units)
    return {
        "city": raw["name"],
        "temperature": raw["main"]["temp"],
        "condition": raw["weather"][0]["description"],
        ...
    }

# ❌ WRONG — leaks API schema into agent layer
return requests.get(url).json()
```

### 8. Input validation on all public methods

```python
# ✅ CORRECT
def get_weather_summary(self, city: str, temperature_units: str = "imperial") -> str:
    if not city or not isinstance(city, str) or not city.strip():
        raise ValueError("city must be a non-empty string")
    if temperature_units not in ("imperial", "metric", "standard"):
        raise ValueError(f"temperature_units must be imperial|metric|standard, got {temperature_units!r}")
```

### 9. Config access via ConfigManager — never os.environ directly in agents/tools

```python
# ✅ CORRECT
api_key = self.config_manager.get("env.weather_api_key")

# ❌ WRONG
import os
api_key = os.environ["WEATHER_API_KEY"]
```

### 10. Tests — unit tests must be hermetic (no network, no LLM)

```python
# ✅ CORRECT — mock the HTTP call
from unittest.mock import patch, MagicMock

def test_get_temperature_success():
    with patch("src.tools.weather_tool.requests.get") as mock_get:
        mock_get.return_value.json.return_value = {...}
        mock_get.return_value.status_code = 200
        client = WeatherClient(mock_config)
        result = client.get_temperature("Seattle")
        assert result["city"] == "Seattle"

# ❌ WRONG — hits real API in a unit test
def test_get_temperature():
    client = WeatherClient(real_config)
    result = client.get_temperature("Seattle")   # flaky, slow, costs API calls
```

---

## Patterns Copilot must NOT suggest (reject these)

- `from src.providers.ollama_provider import OllamaClient` inside an agent — use `BaseLLMProvider`
- `logging.basicConfig()` anywhere in `src/`
- `print()` in `src/` (only acceptable in `main.py` for CLI output)
- Bare `except:` or `except Exception: pass`
- `import os; os.environ[...]` inside agents or tools
- Direct `requests.get()` calls in agents — tools own HTTP
- LangChain imports — we own the orchestration layer
- `global` variables for config or clients
- Hardcoded paths like `"../configs/config.yaml"` — use `Path(__file__).parent`

---

## File naming conventions

| Type | Convention | Example |
|---|---|---|
| Agent | `{domain}_agent.py` | `weather_agent.py` |
| Tool | `{api_name}_tool.py` | `weather_tool.py` |
| Provider | `{name}_provider.py` | `ollama_provider.py` |
| Test | `test_{module}.py` | `test_weather_agent.py` |
| Exception class | `{Domain}Error` | `WeatherAgentError` |

---

## When Copilot suggests adding a new agent

It must produce ALL of the following or the PR will be rejected:

1. `src/agents/{domain}_agent.py` with `BaseAgent` inheritance
2. `src/tools/{api}_tool.py` if a new external API is needed
3. `tests/unit/test_{domain}_tool.py` with mocked HTTP
4. `tests/integration/test_{domain}_agent.py` marked `@pytest.mark.integration`
5. Updated `docs/AGENTS.md` agent registry table
6. New config keys added to `configs/config.yaml.example`

---

## Current phase (Phase 1)

Phase 1 tasks in priority order:
1. Create `src/providers/base_provider.py` — `BaseLLMProvider` ABC
2. Update `OllamaClient` to extend `BaseLLMProvider`
3. Create `src/providers/claude_provider.py` — `ClaudeProvider`
4. Create `src/providers/provider_factory.py` — `get_provider(config)`
5. Update `WeatherAgent` to accept `BaseLLMProvider` (not `OllamaClient`)
6. Populate `.github/workflows/ci.yml`
7. Add `ruff` and `mypy` configs to `pyproject.toml`
8. Add unit tests to reach 60% coverage

Do not start Phase 2 (tool registry) until Phase 1 definition of done is checked off in PLAN.md.

---

## Copilot chat prompts that work well in this repo

- "Generate a BaseAgent abstract class following the pattern in AGENTS.md"
- "Write a unit test for WeatherTool.get_temperature that mocks requests.get"
- "Add input validation to this agent method following the existing WeatherAgent pattern"
- "Write a ClaudeProvider that implements BaseLLMProvider"
- "Explain what this exception hierarchy covers and what's missing"