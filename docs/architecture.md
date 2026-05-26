# Architecture & Design — em-ai-labs

## 1. System context

```
┌──────────────────────────────────────────────────────────────┐
│                        User / Client                          │
│           (CLI · future: web UI · API endpoint)               │
└─────────────────────────┬────────────────────────────────────┘
                          │ natural language goal
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                      Orchestrator                             │
│   Plans tasks · routes to agents · handles retries & errors  │
└──────┬─────────────────┬────────────────────┬───────────────┘
       │                 │                    │
       ▼                 ▼                    ▼
┌────────────┐  ┌────────────────┐  ┌─────────────────┐
│WeatherAgent│  │ FinanceAgent   │  │   MusicAgent    │  ...
│            │  │  (Phase 4)     │  │   (Phase 4)     │
└──────┬─────┘  └───────┬────────┘  └────────┬────────┘
       │                │                    │
       ▼                ▼                    ▼
┌────────────┐  ┌────────────────┐  ┌─────────────────┐
│WeatherTool │  │CalculatorTool  │  │  SpotifyTool    │
│(Phase 1 ✅)│  │  (Phase 2)     │  │   (Phase 4)     │
└──────┬─────┘  └───────┬────────┘  └────────┬────────┘
       └────────────────┴────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   BaseLLMProvider    │  ← abstract interface
              ├──────────┬───────────┤
              │  Ollama  │  Claude   │  (swap via config, zero code change)
              └──────────┴───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │       Memory         │
              ├──────────────────────┤
              │ ConversationMemory   │  short-term (in-process)
              │ ChromaDB             │  long-term semantic (Phase 3)
              └──────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Observability       │
              │  logging · tracing   │
              │  guardrails · evals  │
              └──────────────────────┘
```

---

## 2. Loose coupling — the design contract

The harness is built around three abstract base classes. **No concrete class imports another concrete class directly.** Everything communicates through interfaces.

```
BaseLLMProvider          BaseTool              BaseAgent
─────────────            ─────────             ──────────
chat_completion()        execute(input)        run(goal)
health_check()           schema → dict         name → str
model_name → str         name → str            tools → list[BaseTool]
                                               provider → BaseLLMProvider
```

Agents receive their provider and tools **injected from outside** (dependency injection). This means:
- You can test an agent with a mock provider — no Ollama required.
- You can swap from Ollama to Claude by changing one config line.
- A new contributor can add a tool without touching any agent file.

---

## 3. Request flow — WeatherAgent (current, production-ready)

```
main.py
  │  user types "What's the weather in Seattle?"
  ▼
WeatherAgent.get_weather_summary("Seattle")
  │
  ├─► WeatherTool.get_temperature("Seattle", units="imperial")
  │     │  HTTP GET → OpenWeatherMap API
  │     │  Returns: {city, temp, condition, humidity, ...}
  │     └─► WeatherAPIError on failure (caught, logged, re-raised as WeatherAgentExecutionError)
  │
  ├─► _format_weather_prompt(weather_data)   → structured LLM prompt
  │
  └─► OllamaClient.chat_completion(prompt, system_prompt)
        │  POST → http://localhost:11434/api/chat
        └─► Returns: "🌡️ Seattle is 52°F with drizzle — typical for May!"
```

---

## 4. Request flow — Orchestrator (Phase 4 target)

```
User: "How much house can I afford on a $180k salary in Seattle?"
  │
  ▼
Orchestrator.run(goal)
  │
  ├─ 1. Plan (LLM call):
  │       → ["FinanceAgent: mortgage calc", "FinanceAgent: budget analysis"]
  │
  ├─ 2. Execute FinanceAgent.run(mortgage_params)
  │       ├─► CalculatorTool.amortize(price, rate, term)
  │       ├─► CalculatorTool.dti_ratio(income, debts)
  │       └─► LLM: "Given these numbers, here's what you can afford..."
  │
  ├─ 3. Memory: store result in ChromaDB under user_id namespace
  │
  └─ 4. Return synthesized response + source trace
```

---

## 5. Provider abstraction (Phase 1 — in progress)

```python
# agents ONLY ever see this interface:
class BaseLLMProvider(ABC):
    def chat_completion(self, messages, system_prompt=None) -> str: ...
    def health_check(self) -> bool: ...
    @property
    def model_name(self) -> str: ...

# config.yaml drives which provider is instantiated:
# llm:
#   provider: ollama   ← or 'claude'

# one factory, no if/else scattered across the codebase:
provider = get_provider(config_manager)   # returns OllamaProvider or ClaudeProvider
agent = WeatherAgent(provider=provider)   # agent doesn't know or care which one
```

---

## 6. Exception hierarchy (current)

```
Exception
├── OllamaError
│   ├── ConfigError
│   ├── ModelNotFoundError
│   └── OllamaConnectionError
├── WeatherError
│   ├── WeatherConfigError
│   ├── WeatherAPIError
│   └── CityNotFoundError
└── WeatherAgentError
    ├── WeatherAgentInitError
    └── WeatherAgentExecutionError

Phase 1+ additions:
├── ProviderError            ← base for all LLM provider failures
│   ├── ProviderNotFoundError
│   └── ProviderAuthError
└── AgentError               ← base for all agent failures (replaces per-agent bases)
    ├── AgentInitError
    └── AgentExecutionError
```

---

## 7. Logging contract

Every module follows this pattern:

```python
import logging
logger = logging.getLogger(__name__)   # module-scoped, never root logger

# structured log levels:
logger.debug("Fetching weather data for city=%s units=%s", city, units)
logger.info("WeatherAgent initialized model=%s", self.provider.model_name)
logger.warning("Retrying request attempt=%s/%s", attempt, max_retries)
logger.error("WeatherTool failed city=%s error=%s", city, e, exc_info=True)
```

**What we do NOT do:**
- `print()` in production code (use `logger.debug`)
- `logging.basicConfig()` inside library modules (caller configures logging)
- Log API keys, full prompts with PII, or raw weather payloads at INFO level

---

## 8. Configuration loading order

```
1. configs/config.yaml.example   ← committed, safe template
2. configs/config.yaml           ← local override, git-ignored
3. configs/.env                  ← secrets, git-ignored
4. OS environment variables      ← highest priority (overrides .env)

ConfigManager resolves: config.get("env.weather_api_key")
  → reads WEATHER_API_KEY from .env / env var
  → never stores plaintext in config.yaml
```

---

## 9. Test strategy

```
tests/
├── unit/                    ← fast, no network, no LLM
│   ├── test_config_manager.py
│   ├── test_base_provider.py    (ABC enforcement, factory routing)
│   ├── test_weather_tool.py     (mock HTTP responses)
│   └── test_base_tool.py        (Phase 2)
└── integration/             ← require external services, marked @pytest.mark.integration
    ├── test_weather_agent.py    (real Ollama + real Weather API)
    └── test_ollama_provider.py  (real Ollama health check)

CI runs:   pytest tests/unit/ -v           ← always, no services needed
Dev runs:  pytest -v                       ← all tests including integration
```

---

## 10. Phase milestones & architecture changes per phase

| Phase | Key architecture change | New files |
|---|---|---|
| 1 (now) | Provider abstraction · CI · installable | `base_provider.py`, `claude_provider.py`, `provider_factory.py`, `ci.yml` |
| 2 | Tool registry · BaseTool auto-discovery | `base_tool.py`, `calculator_tool.py`, `tool_registry.py` |
| 3 | Memory layer | `conversation_memory.py`, `chroma_memory.py` |
| 4 | Orchestrator | `orchestrator.py`, `finance_agent.py`, `music_agent.py` |
| 5 | Observability & guardrails | `tracing.py`, `guardrails.py`, `evals/` |

---

## Architecture Decision Records

See `docs/ADR/` for decisions and their rationale:

- `ADR-001-provider-abstraction.md` — why ABC over protocol
- `ADR-002-ollama-first.md` — local-first LLM strategy
- `ADR-003-chromadb-for-memory.md` — why ChromaDB over Pinecone for Phase 3
- `ADR-004-no-langchain-orchestrator.md` — why we own orchestration