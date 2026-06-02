# Architecture & design — em-ai-labs

> Last updated: May 2026 · reflects master branch with orchestration

---

## 1. System overview

```
User / Client
     │  natural language goal
     ▼
AgentManager                    ← bootstrap, correlation ID, top-level error handling
     │
     ▼
Orchestrator                    ← async run(goal, session_id)
  ├── Planner                   ← create_plan() → list[Task]
  ├── ReACTLoop                 ← iterate up to max_iterations
  │     └── Executor            ← execute_task() / execute_parallel()
  │           ├── MessageRouter ← keyword + regex scoring → agent_name
  │           └── AgentRegistry ← pkgutil discovery → AgentFactory → agent instance
  └── synthesize(results)       ← join outputs into final response
         │
         ▼
     WeatherAgent (+ future: FinanceAgent, MusicAgent …)
         ├── BaseLLMProvider    ← OllamaClient | ClaudeProvider
         ├── WeatherTool        ← OpenWeatherMap API
         └── InProcessMemory    ← session-partitioned chat history

Supporting layers (all layers):
  ServiceContainer              ← DI root: provider + tool_registry
  ConfigManager                 ← YAML + .env, layered, get_required()
  logging_utils                 ← StructuredFormatter JSON, ContextVar correlation IDs
  log_filters                   ← PIIRedactionFilter on file handler
```

---

## 2. Request lifecycle (step by step)

```
1.  User sends message
2.  AgentManager.handle(message)
      → set_correlation_id()          # new UUID per request
      → orchestrator.run(goal, session_id=request_id)

3.  Orchestrator.run()
      → memory_context = []           # TODO: load from InProcessMemory
      → ExecutionContext(session_id, goal, memory)
      → react_loop.run(goal, context)

4.  ReACTLoop.run()
      → planner.create_plan(goal, context)
            returns [Task(id, description)]   # currently single-task; LLM decomp in Phase 4+
      → for each task: executor.execute_task(task, context)
      → break after first successful cycle   # loop scaffolding in place, not yet iterating

5.  Executor.execute_task(task, context)
      → task.status = RUNNING
      → router.route_task(task)              # → agent_name
      → agent_registry.get(agent_name)
      → await agent.handle(task, context)
      → task.status = COMPLETED
      → context.completed_tasks[task.id] = result

6.  WeatherAgent.handle(task, context)
      → extract_city(task.description)
      → weather_tool.get_temperature(city)   # OpenWeatherMap
      → provider.chat_completion(prompt)     # Ollama or Claude
      → return summary string

7.  Orchestrator.synthesize(results)
      → "\n".join(results)                   # TODO: LLM synthesis call

8.  AgentManager returns response
      → reset_correlation_id() in finally
```

---

## 3. Module map

```
src/
├── agent_manager.py            # top-level entry point, AgentManager class
├── router.py                   # MessageRouter, route_message(), get_router()
│
├── core/
│   └── container.py            # ServiceContainer — DI root, builds provider + tool_registry
│
├── orchestration/
│   ├── orchestrator.py         # Orchestrator — coordinates all sub-components
│   ├── planner.py              # Planner — goal → list[Task]
│   ├── react_loop.py           # ReACTLoop — iterative reason+act loop
│   ├── executor.py             # Executor — run single or parallel tasks
│   ├── task_graph.py           # TaskGraph — dependency resolution, ready-task detection
│   └── models.py               # Task, ExecutionContext, TaskStatus (dataclasses + enum)
│
├── agents/
│   ├── base_agent.py           # BaseAgent ABC, AgentError hierarchy
│   ├── agent_factory.py        # AgentFactory — constructor introspection DI
│   ├── agent_registry.py       # AgentRegistry — pkgutil auto-discovery
│   └── weather_agent.py        # WeatherAgent — production agent #1
│
├── providers/
│   ├── base_provider.py        # BaseLLMProvider ABC
│   ├── ollama_provider.py      # OllamaClient
│   ├── claude_provider.py      # ClaudeProvider
│   └── provider_factory.py     # ProviderFactory.get_provider(config)
│
├── tools/
│   ├── base_tool.py            # BaseTool ABC, _safe_execute()
│   ├── tool_registry.py        # ToolRegistry — pkgutil auto-discovery
│   ├── weather_tool.py         # OpenWeatherMap client
│   ├── web_search_tool.py      # DuckDuckGo search
│   ├── vision_extractor.py     # PDF/image → transactions
│   └── gsheets_tool.py         # Google Sheets read/write
│
├── memory/
│   ├── base_memory.py          # BaseMemory ABC
│   └── conversation_memory.py  # InProcessMemory (+ duplicate BaseMemory — see known bugs)
│
└── utils/
    ├── config_loader.py        # ConfigManager — YAML + .env, get_required(), validate_startup()
    ├── logging_utils.py        # StructuredFormatter, correlation ID ContextVars
    └── log_filters.py          # PIIRedactionFilter — email, hex keys, Bearer tokens
```

---

## 4. Key design patterns

### Dependency injection everywhere

Nothing creates its own dependencies. `ServiceContainer` is the single construction site.
`AgentFactory` uses constructor introspection to resolve `config_manager`, `base_llm_provider`,
and named tools by parameter name — no hardcoded wiring.

```python
# AgentFactory resolves dependencies by parameter name:
class WeatherAgent(BaseAgent):
    def __init__(self, config_manager, base_llm_provider, weather_tool):
        ...
# AgentFactory inspects __init__, matches params to container attributes, injects.
```

### Abstract base classes enforce contracts

`BaseLLMProvider`, `BaseTool`, `BaseAgent`, `BaseMemory` — all are ABCs.
Python raises `TypeError` at instantiation time if a subclass skips an abstract method.
No runtime surprises.

### Auto-discovery for agents and tools

Both `AgentRegistry` and `ToolRegistry` use `pkgutil.iter_modules` + `importlib.import_module`
to scan their respective packages on startup. Adding a new agent or tool requires only:
1. Create the file in `src/agents/` or `src/tools/`
2. Inherit `BaseAgent` or `BaseTool`
3. Implement the abstract methods

No manual registration, no imports in `__init__.py`.

### Structured JSON logging with correlation IDs

Every log line is JSON with `timestamp`, `level`, `logger`, `message`, `correlation_id`,
`service`, `environment`, `host`, and any `extra_data` dict.
Correlation ID is a ContextVar set once per request in `AgentManager.handle()`.
PIIRedactionFilter strips emails, hex API keys, and Bearer tokens from file handler output.

### Exception hierarchy

```
Exception
├── AgentError
│   ├── AgentInitError
│   └── AgentExecutionError
│       └── WeatherAgentExecutionError
├── (provider errors — in each provider module)
└── (tool errors — in each tool module)
```

Never raise bare `Exception`. Never catch bare `Exception` without re-raising as a typed error.

---

## 5. Data models

### Task

```python
@dataclass
class Task:
    id: str                          # UUID4
    description: str                 # the goal text passed to the agent
    assigned_agent: str | None       # None = router decides
    dependencies: list[str]          # list of task IDs that must complete first
    parallelizable: bool             # if True, executor can run concurrently
    status: TaskStatus               # PENDING | RUNNING | COMPLETED | FAILED
    result: Any                      # filled by executor after completion
```

### ExecutionContext

```python
@dataclass
class ExecutionContext:
    session_id: str
    goal: str
    memory: list[str]                # TODO: populated from InProcessMemory
    completed_tasks: dict[str, Any]  # task_id → result, grows during execution
    metadata: dict[str, Any]         # extensible for future use
```

### TaskStatus lifecycle

```
PENDING → RUNNING → COMPLETED
                 ↘ FAILED
```

---

## 6. Configuration loading order

```
1. configs/config.yaml.example    ← committed, safe template
2. configs/config.yaml            ← local override, git-ignored
3. configs/.env                   ← secrets, git-ignored
4. OS environment variables       ← highest priority, overrides everything

ConfigManager.get("env.WEATHER_API_KEY")
  → reads WEATHER_API_KEY from .env / OS env
  → never stored in config.yaml

ConfigManager.get_required("env.WEATHER_API_KEY")
  → raises ConfigError immediately if missing
  → called from validate_startup() at boot
```

---

## 7. CI pipeline

```
Every push / PR to master:

  static-analysis          (~30s)
    ruff check + format
    (mypy — enable later)

  security                 (~45s)
    bandit -ll --skip B101
    pip-audit (documented ignores in .pip-audit.toml)

  unit-tests               (~60s, Python 3.11 + 3.12)
    pytest tests/unit/
    --cov-fail-under=60
    OLLAMA_HOST="" WEATHER_API_KEY="" ANTHROPIC_API_KEY=""

  integration-tests        (~3 min, owner repo + push only)
    install + start Ollama (30s readiness loop)
    verify model loaded
    pytest tests/integration/ -m integration --no-cov

Every Monday 9am UTC:
  security.yml
    pip-audit CVE scan → artifact
    gitleaks secret scan (full history)
```

---

## 8. Known bugs (fix before Phase 4)

| Bug | File | Symptom | Fix |
|---|---|---|---|
| `health_check()` references `self.tool_registry` | `agent_manager.py` | AttributeError at runtime | Change to `self.container.tool_registry` |
| `route_task()` calls global `route_message()` | `router.py` | Bypasses instance config | Change to `self.route_message(task.description)` |
| Module-level `route_task(self, task)` free function | `router.py` | Invalid Python (`self` param) | Delete the module-level duplicate |
| Duplicate `BaseMemory` ABC | `conversation_memory.py` | Two sources of truth | Import from `base_memory.py` instead |
| `context.memory` never populated | `orchestrator.py` | Memory layer constructed but unused | Wire `InProcessMemory.get_history()` into context |
| `pyproject.toml` coverage gate = 60% | `pyproject.toml` | Local pytest gives false confidence | Change to `--cov-fail-under=60` |

---

## 9. Roadmap

| Phase | Focus | Status |
|---|---|---|
| 1 | Provider abstraction, CI, BaseAgent | ✅ Done |
| 2 | ToolRegistry, BaseMemory, observability | ✅ Done |
| 3 | Orchestrator scaffold, ReACTLoop, TaskGraph | ✅ Done (scaffold) |
| 3b | Fix known bugs, wire memory, LLM planner | 🔄 Now |
| 4 | FinanceAgent, CalculatorTool, LLM synthesis, home finance app | 📋 Next |
| 5 | OTel tracing, guardrails, eval framework, HTTP health endpoint | 📋 Future |