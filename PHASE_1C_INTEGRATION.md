# Phase 1C: Runtime Factory & Integration

## Current status

This phase implements config-driven runtime selection and integrates the new LangChain runtime with existing tools.

### Completed
- `src/runtimes/runtime_factory.py` created
- `src/main.py` updated to use `RuntimeFactory.create(...)`
- `src/main.py` now routes with `MessageRouter.route_message(...)`
- `src/runtimes/custom_runtime.py` placeholder created for Phase 2

### Pending
- Verify runtime initialization works end-to-end
- Verify `WeatherClient` and `WebSearchClient` can be loaded as LangChain tools
- Confirm `ConfigManager.validate_startup()` passes with current config
- Add integration tests in Phase 3 once runtime calls are working

## Notes
- `runtime.orchestration` is now set to `langchain` in `configs/config.yaml`
- If `custom` is selected, `CustomRuntime` raises a clear "not implemented" error
- `main.py` uses structured logging and correlation IDs

## How to run later
1. Ensure `venv` is active.
2. Install dependencies from `requirements.txt`.
3. Start Ollama locally and ensure the configured model is available.
4. Run:
   ```powershell
   python src/main.py
   ```
5. Ask:
   - "What's the weather in London?"
   - "Search for Python best practices"

## Next step
- Continue with Phase 3: testing and verification
- Add runtime health checks and telemetry validation
