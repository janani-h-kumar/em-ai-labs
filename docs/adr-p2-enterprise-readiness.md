### Why Enterprise Readiness Matters

The repository is positioned as an agent harness for local LLM models in enterprise environments, not a hobby demo. That means the architecture should favor explicit dependency ownership, predictable discovery, and configurable backend selection while avoiding premature complexity.

---

## Status

Proposed

---

## Context

Current repo strengths:

- `src/core/container.py` exists and owns `ConfigManager`, `ProviderFactory` output, `ToolRegistry`, and `Memory`.
- `AgentRegistry` auto-discovers `BaseAgent` subclasses in `src.agents`.
- `ToolRegistry` auto-discovers `BaseTool` subclasses in `src.tools`.
- `ServiceContainer` is the intended composition root.

Current gaps:

- `ServiceContainer` still instantiates `InProcessMemory` directly, preventing memory backend selection or discovery.
- Memory remains implemented as a single backend; there is no memory registry or auto-discovery mechanism.
- Architecture docs and diagrams are generally current, but they do not explicitly call out memory backend discovery or the `AgentDescriptor` metadata contract.
- The repo is enterprise-focused, so the harness needs a stronger, minimal plugin model for memory and provider selection.

---

## Decision

1. Keep `ServiceContainer` as the single holder of shared infrastructure. It must own:
   - `ConfigManager`
   - `BaseLLMProvider` / provider factory output
   - `ToolRegistry`
   - `MemoryRegistry` / memory backend
   - `Telemetry` or observability hooks (future)

2. Preserve auto-discovery for agents and tools.
   - `AgentRegistry` must continue discovering all `BaseAgent` subclasses from `src.agents`.
   - `ToolRegistry` must continue discovering all `BaseTool` subclasses from `src.tools`.

3. Introduce memory discovery.
   - Add a memory plugin registry or factory that scans `src.memory`.
   - Keep the interface simple: `BaseMemory.get_history(session_id)` and `BaseMemory.clear(session_id)`.
   - Default to `InProcessMemory`, but allow alternate backends via config.

4. Update architecture documentation.
   - Ensure diagrams show the composition root, tool discovery, agent discovery, memory backend selection, and provider selection.
   - Keep diagrams simple: a container owns provider/tool/memory, registry discovers agents, orchestrator retrieves memory.

5. Avoid over-engineering.
   - Do not introduce a full plugin framework or service bus yet.
   - Implement discovery and selection with package scanning and config-driven backend choice.
   - Keep the ReACT loop and execution context lightweight.

---

## Consequences

### Benefits

- Clear enterprise composition model
- Configurable memory backend for local and cloud deployments
- Explicit dependency ownership in the container
- Tools and agents remain auto-discoverable
- Documentation reflects actual service boundaries

### Tradeoffs

- Adds one more registry concept for memory
- Requires a small amount of new wiring in `ServiceContainer`
- Slightly more explicit config required for non-default memory backends

---

## Implementation Notes

- `ServiceContainer` should instantiate a memory registry/factory rather than hardcoded `InProcessMemory`.
- `AgentRegistry` should keep metadata descriptors so router and health checks can work without agent instantiation.
- `ToolRegistry` and `AgentRegistry` are already auto-discoverable; no change is required there except documentation clarifications.
- Add a lightweight config key such as:

```yaml
memory:
   # Preferred: explicit memory backend selection. Values are keys discovered by
   # `MemoryRegistry` (e.g. "memory" for the in-process implementation).
   backend: "memory"        # e.g. "memory" | "sqlite" | "redis"
   options:
      ttl_seconds: 3600

Notes:
   - `ServiceContainer` resolves the selected backend by consulting
      `MemoryRegistry` and instantiating via `MemoryFactory`.
   - If `memory.backend` is not set the container falls back to
      `persistence.type` (the historical config key) and finally to
      the default backend name of `memory`.
   - The in-process implementation (`InProcessMemory`) registers as
      `name = "memory"` so it matches the default config value above.
```

- Add docs to `docs/architecture.md` and `docs/ARCHITECTURE-DIAGRAMS.md` showing memory backend discovery.

Runtime note
------------

- `LangChainRuntime` currently accepts an optional `memory` parameter and will
   fall back to an `InProcessMemory()` instance if `None` is provided. With the
   `ServiceContainer` wiring described above, the container will supply the
   configured memory instance and runtime consumers should prefer the injected
   memory. Consider removing the internal fallback in `LangChainRuntime` to
   enforce explicit DI in future iterations.

---

## Follow-up

Create a minimal `MemoryRegistry` or `MemoryFactory` and update `ServiceContainer` to use it.
Update `docs/architecture.md` with a refreshed component diagram showing memory discovery.
Add tests for memory backend selection and default memory discovery.
