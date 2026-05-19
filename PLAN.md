# Plan: Production-Grade Ollama Interactive Chat with Extensible Agent Architecture

## Phase 1: Interactive Chat App (Current Focus)
**Status**: Implementation in Progress

### Overview
Build an interactive terminal chat application that supports:
- Real-time user input with multi-turn conversations
- Session-level and persistent conversation history
- Extensible architecture for future agent harness and guardrails

### Architecture Decision
- **Interactive Chat Layer**: Terminal UI, input handling, conversation loop
- **Agent Abstraction**: Interface for different agent implementations (future-proof)
- **Persistence Layer**: Optional SQLite storage for conversations
- **Configuration**: YAML-based for extensibility

### Current Implementation (Phase 1 Only)
1. `Samples/interactive_chat.py` - Main terminal chat app
   - User input loop with exit/command handling
   - Conversation history management
   - Integration with OllamaClient
   
2. `Samples/config.yaml` - Extensible configuration
   - Model settings
   - Persistence options (in-memory or SQLite)
   - Chat settings (timeout, max history, etc.)

3. `.gitignore`, `README.md`, `config.json.example` - Security & documentation

### Future Phases (Placeholder for Plan)
**Phase 2: Agent Harness** (will be designed later)
- Agent registry/factory pattern
- Agent interface abstraction
- Multi-agent orchestration
- Agent routing logic

**Phase 3: Guardrails** (will be added incrementally)
- Safety/toxicity filtering
- Prompt injection protection
- Cost/rate limiting
- Context validation
- Output filtering

---

## Files Structure (Post-Implementation)

```
ai-lab/
├── requirements.txt
├── README.md
├── PLAN.md (this file)
├── .gitignore
├── venv/
└── Samples/
    ├── ollama_client.py          # Existing: Core client
    ├── interactive_chat.py       # NEW: Chat application
    ├── config.yaml               # NEW: Configuration
    ├── config.yaml.example       # NEW: Config template
    ├── config.json               # Local only (git-ignored) 
    ├── config.json.example       # Existing
    ├── test_local_llm.py         # Existing
    ├── agent_interface.py        # FUTURE: Agent abstraction
    ├── agent_registry.py         # FUTURE: Agent management
    ├── guardrails/               # FUTURE: Guardrails modules
    └── persistence/              # FUTURE: Persistence layer
```

---

## User Preferences (Current)
- **Guardrails**: Do NOT implement now. Will add one by one later. Keep checklist for reference.
- **Persistence**: Both options configurable (in-memory default, SQLite optional)
- **Extensibility**: Design for easy agent addition (registry pattern planned for Phase 2)
- **Focus**: Interactive chat app ONLY right now
- **Learning Mode**: User will write different agents incrementally

### Future Guardrails Checklist (To Be Implemented Later)
- [ ] Safety/toxicity filtering
- [ ] Prompt injection protection
- [ ] Cost/rate limiting
- [ ] Context validation
- [ ] Output filtering

---

## Dependency & API Compatibility (Long-Term Prevention)
- Pin runtime-critical libraries in `requirements.txt` for every runtime integration.
- Verify actual package exports before editing code, for example:
  - `python -c "import langchain.agents as a; print(dir(a))"`
  - `python -c "from langchain.agents import create_agent; import inspect; print(inspect.signature(create_agent))"`
- Avoid stale API names such as `AgentExecutor` or `create_openai_tools_agent` unless the pinned LangChain version explicitly supports them.
- When upgrading packages, update the runtime code and plan documentation together.
- Always run minimal validation after changes:
  - `python -m py_compile src/main.py src/runtimes/langchain_runtime.py`
  - `python -c "from src.main import AgentManager"`

---

## Phase 1: Interactive Chat Implementation Steps

### Step 1: Update requirements.txt ✅
Add `pyyaml` for YAML configuration support

### Step 2: Create config.yaml ✅
Main configuration file for interactive chat

### Step 3: Create config.yaml.example ✅
Template for users to copy and customize

### Step 4: Create interactive_chat.py ✅
Features:
- Terminal loop with user input
- Conversation history (in-memory list of dicts)
- Command handling: exit, clear, help, model, history, save
- Multi-turn support using existing chat_completion()
- Clean formatting with emojis and separators

Commands:
- `exit`, `quit`, `close`, `bye`, `goodbye` → Exit app
- `clear` → Reset conversation history
- `help` → Show available commands
- `model` → Show current model name
- `history` → Display full conversation
- `save` → Export conversation to file

### Step 5: Update README.md ✅
Add interactive chat usage section

### Step 6: Test ✅
Verify all functionality works

---

## Design Decisions for Future Extensibility

### Agent Architecture (Stub for Phase 2)
```python
# agent_interface.py (FUTURE - NOT IN PHASE 1)
from abc import ABC, abstractmethod
from typing import Dict, List

class AgentInterface(ABC):
    """Base class for all agents"""
    
    @abstractmethod
    async def process(self, message: str, context: Dict) -> str:
        """Process message and return response"""
        pass
    
    def get_name(self) -> str:
        """Return agent name"""
        pass

# Current implementation
class OllamaAgent(AgentInterface):
    """Ollama-based agent"""
    
    def __init__(self, config_manager):
        self.ollama = OllamaClient(config_manager)
    
    async def process(self, message: str, context: Dict) -> str:
        return self.ollama.chat_completion(context)
```

### Registry Pattern (Stub for Phase 2)
```python
# agent_registry.py (FUTURE - NOT IN PHASE 1)
class AgentRegistry:
    """Registry for dynamic agent loading"""
    
    _agents = {}
    
    @classmethod
    def register(cls, name: str, agent_class):
        cls._agents[name] = agent_class
    
    @classmethod
    def get(cls, name: str):
        return cls._agents.get(name)
```

### Persistence Pattern (Stub for Phase 3)
```python
# persistence/conversation_store.py (FUTURE - OPTIONAL IN PHASE 1)
from abc import ABC, abstractmethod

class ConversationStore(ABC):
    """Abstract store interface"""
    
    @abstractmethod
    def save(self, conversation: List[Dict]) -> str:
        pass
    
    @abstractmethod
    def load(self, session_id: str) -> List[Dict]:
        pass

class MemoryStore(ConversationStore):
    """In-memory storage (Phase 1)"""
    pass

class SQLiteStore(ConversationStore):
    """SQLite storage (Future)"""
    pass
```

---

## Data Flow Architecture (Future-Proof)

```
User Input
    ↓
Guardrails (INPUT) [Phase 3 - NOT YET]
    ↓
Agent Registry lookup [Phase 2 - NOT YET]
    ↓
Selected Agent processes message [Phase 2 - NOT YET]
    ↓
Guardrails (OUTPUT) [Phase 3 - NOT YET]
    ↓
Response formatted & displayed
    ↓
Conversation Store (if enabled) [Phase 1 - in-memory only]
```

---

## Verification (Phase 1)
1. ✅ Run `python interactive_chat.py` and chat normally
2. ✅ Verify conversation history is maintained across turns
3. ✅ Test exit commands (exit, quit, close, bye, goodbye)
4. ✅ Test `clear` command resets history
5. ✅ Test `help` command displays available commands
6. ✅ Test `model` command shows current model
7. ✅ Verify `config.yaml` is loaded correctly
8. ✅ Test `history` command shows full conversation
9. ✅ Test `save` command exports conversation

---

## Implementation Order (Phase 1)

**Priority 1 (MVP):**
1. ✅ Create config.yaml and config.yaml.example
2. ✅ Update requirements.txt with pyyaml
3. ✅ Create interactive_chat.py with core loop and basic commands
4. ✅ Update README.md with usage instructions

**Priority 2 (Testing):**
5. ✅ Test interactive chat app with multiple turns
6. ✅ Test all commands work correctly

---

## Dependencies
- Python 3.8+
- `openai` (existing)
- `requests` (existing)
- `pyyaml` (new - for YAML configuration)

---

## Current Status
- ✅ Architecture Design: Complete
- ✅ Phase 1 Plan: Complete (this document)
- ⏳ Phase 1 Implementation: In Progress
- 📋 Phase 2 Design: To be created when needed
- 📋 Phase 3 Design: To be created when needed

---

## Notes
- **No guardrails implemented now** — Listed with checkboxes for future
- **No agent harness now** — Will be built in Phase 2
- **Learning-focused** — User will write agents incrementally; architecture supports this
- **Persistence optional** — Default in-memory for Phase 1
- **YAML configuration** — More extensible than JSON for future features
