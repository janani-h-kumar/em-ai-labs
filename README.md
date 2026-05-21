# em-ai-labs — Enterprise AI Agent Harness

> **Goal**: Build a production-grade, loosely coupled AI agent harness in Python — from a local Ollama client to a fully orchestrated, observable, multi-agent enterprise system.

[![CI](https://github.com/janani-h-kumar/em-ai-labs/actions/workflows/ci.yml/badge.svg)](https://github.com/janani-h-kumar/em-ai-labs/actions)
[![Coverage](https://img.shields.io/badge/coverage-60%25-yellow)](https://github.com/janani-h-kumar/em-ai-labs)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Architecture overview

```
User / Orchestrator App
        │
   Orchestrator                ← plans, routes, retries  [Phase 4]
   ┌────┴──────┐
WeatherAgent  FinanceAgent  MusicAgent ...              ← Agent pool [current]
   │                │
WeatherTool   CalculatorTool  SpotifyTool ...           ← Tool registry [Phase 2]
   │
BaseLLMProvider ──► OllamaProvider | ClaudeProvider    ← Provider layer [Phase 1]
   │
Memory (ConversationMemory → ChromaDB)                 ← Memory layer [Phase 3]
   │
Observability (logging → OpenTelemetry → Jaeger)       ← O11y layer [Phase 5]
```

---

## Repository structure

```
em-ai-labs/
├── .github/
│   └── workflows/
│       ├── ci.yml                  # Lint, type-check, test on every push
│       └── security.yml            # Bandit + pip-audit weekly
├── configs/
│   ├── config.yaml                 # Local config (git-ignored)
│   ├── config.yaml.example         # Template — copy to config.yaml
│   └── .env                        # Secrets (git-ignored)
├── docs/
│   ├── ARCHITECTURE.md             # System design & flow diagrams
│   ├── AGENTS.md                   # Agent standards & onboarding guide
│   ├── CONTRIBUTING.md             # PR process, branch strategy
│   └── ADR/                        # Architecture Decision Records
├── requirements/
│   ├── base.txt                    # Runtime dependencies
│   └── dev.txt                     # Dev/test dependencies
├── src/
│   ├── providers/
│   │   ├── base_provider.py        # BaseLLMProvider ABC  ← Phase 1 TODO
│   │   ├── ollama_provider.py      # Ollama client (+ ConfigManager)
│   │   └── claude_provider.py      # Anthropic client     ← Phase 1 TODO
│   ├── tools/
│   │   ├── base_tool.py            # BaseTool ABC          ← Phase 2 TODO
│   │   └── weather_tool.py         # OpenWeatherMap client
│   ├── agents/
│   │   ├── base_agent.py           # BaseAgent ABC         ← Phase 2 TODO
│   │   ├── weather_agent.py        # ✅ Production-ready
│   │   ├── piano_agent.py          # 🚧 Stub
│   │   └── science_ama_agent.py    # 🚧 Stub
│   └── main.py                     # Interactive CLI entry point
├── tests/
│   ├── unit/
│   │   ├── test_config_manager.py
│   │   ├── test_base_provider.py
│   │   └── test_weather_tool.py
│   └── integration/
│       ├── test_weather_agent.py
│       └── test_ollama_provider.py
├── .env.example
├── .gitignore
├── pyproject.toml                  # Single source of truth for tooling
├── setup.ps1                       # Windows first-time setup
├── AGENTS.md                       # → moved to docs/AGENTS.md
├── PLAN.md                         # Phased roadmap
└── README.md                       # This file
```

---

## Quick start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) running locally, or an Anthropic API key
- OpenWeatherMap API key (free tier, for WeatherAgent)

### First-time setup (Windows)

```powershell
git clone https://github.com/janani-h-kumar/em-ai-labs.git
cd em-ai-labs
.\setup.ps1
```

### First-time setup (Mac / Linux)

```bash
git clone https://github.com/janani-h-kumar/em-ai-labs.git
cd em-ai-labs
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp configs/config.yaml.example configs/config.yaml
cp .env.example configs/.env
# Edit configs/.env — add OLLAMA_HOST, WEATHER_API_KEY, ANTHROPIC_API_KEY
```

### Configure

Edit `configs/.env`:
```
OLLAMA_HOST=http://localhost:11434
OLLAMA_API_KEY=           # leave blank if no auth
WEATHER_API_KEY=          # from openweathermap.org
ANTHROPIC_API_KEY=        # from console.anthropic.com
```

Edit `configs/config.yaml`:
```yaml
llm:
  provider: ollama          # or 'claude'

ollama:
  model: phi3
  timeout: 30

weather:
  base_url: https://api.openweathermap.org/data/2.5
```

### Run

```bash
# Interactive chat
python src/main.py

# Weather agent demo
python src/agents/weather_agent.py

# Run all tests
pytest

# Run only unit tests (no external services needed)
pytest tests/unit/ -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

---

## Agents

See [`docs/AGENTS.md`](docs/AGENTS.md) for the full agent onboarding guide, standards, and checklist.

| Agent | Status | Tools used | Description |
|---|---|---|---|
| `WeatherAgent` | ✅ Ready | `WeatherTool` | AI-powered weather summaries |
| `FinanceAgent` | 📋 Planned | `CalculatorTool` | Mortgage & budget analysis |
| `MusicAgent` | 📋 Planned | `SpotifyTool` | Personalised music for kids |
| `PianoAgent` | 🚧 Stub | — | Music learning companion |
| `ScienceAMAAgent` | 🚧 Stub | — | Science Q&A |

---

## Development

### Running the linter

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Type checking

```bash
mypy src/ --ignore-missing-imports
```

### Security scan

```bash
bandit -r src/ -ll
pip-audit
```

### Adding a new agent

1. Read [`docs/AGENTS.md`](docs/AGENTS.md) — fully.
2. Copy the `BaseAgent` template.
3. Create `src/agents/your_agent.py`.
4. Add tests to `tests/integration/test_your_agent.py`.
5. Update `docs/AGENTS.md` agent registry table.
6. Open a PR — CI must be green.

---

## Roadmap

| Phase | Focus | Status |
|---|---|---|
| 1 | Provider abstraction, CI, installable package | 🔄 In progress |
| 2 | Tool registry, BaseTool, CalculatorTool | 📋 Planned |
| 3 | Memory layer — ConversationMemory + ChromaDB | 📋 Planned |
| 4 | Orchestrator — multi-agent planning & routing | 📋 Planned |
| 5 | Enterprise moat — tracing, guardrails, evals | 📋 Planned |

See [`PLAN.md`](PLAN.md) for detailed tasks per phase.

---

## Security

- `configs/config.yaml` and `configs/.env` are git-ignored — never commit them.
- All credentials load from environment variables via `ConfigManager`.
- `pip-audit` runs weekly in CI to catch dependency CVEs.
- `bandit` scans for common Python security anti-patterns on every push.
- See [GitHub Security tab](https://github.com/janani-h-kumar/em-ai-labs/security) for advisories.

---

## License

MIT — see [LICENSE](LICENSE).