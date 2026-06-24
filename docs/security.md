Accepted Risks (temporary)
--------------------------
- PYSEC-2026-76
- PYSEC-2026-77
- GHSA-gr75-jv2w-4656
- GHSA-f4xh-w4cj-qxq8 (langsmith)
- GHSA-6v7p-g79w-8964 (msgpack)
- GHSA-4xgf-cpjx-pc3j (pydantic-settings)

Rationale
---------
These advisories are currently acknowledged and intentionally ignored in CI
for the reasons below. They are tracked and will be remediated as soon as a
safe, compatible upgrade path is available.

- LangChain-related advisories (PYSEC-2026-76 / 77, GHSA-gr75-jv2w-4656):
  upgrading to LangChain 1.x would require non-trivial code changes across
  the harness and upstream dependencies; we avoid a rushed migration that
  could introduce regressions.

- Transitive advisories (langsmith, msgpack, pydantic-settings):
  these are flagged in transitive dependencies; temporary CI ignores have
  been added while we coordinate upgrades with minimal risk.

Why this is acceptable now
--------------------------
- The current deployment surface does not expose the attack vectors cited in
  the advisories (for example: no untrusted file loaders, no HTML splitter
  ingestion, validated outbound HTTP targets only).
- The ignores are temporary and documented here and in CI comments. We do not
  ignore advisories silently.

Verification & Upgrade Plan
--------------------------
1. Inventory: identify packages that pull in the vulnerable transitive
   dependencies using `pip-audit` and `pipdeptree`.
2. Changelog review: read upgrade notes for candidate direct dependencies
   (LangChain, langchain-core, msgpack consumers, pydantic-settings).
3. Incremental upgrade: pick the smallest safe upgrade (e.g., `msgpack` to
   1.2.1) and pin it in `pyproject.toml` in a feature branch.
4. Test: run unit tests, mypy, ruff, pip-audit, and integration tests locally
   and in CI. Exercise runtime smoke tests (orchestrator + runtime flows).
5. Roll forward: if tests pass, open a PR and require CI; if failures occur,
   fix or revert the pin and iterate.

Commands to reproduce the security check locally (with CI ignores):
```powershell
.venv\Scripts\Activate.ps1
uv sync --extra dev
uv run pip-audit --ignore-vuln GHSA-6w46-j5rx-g56g --ignore-vuln PYSEC-2026-76 --ignore-vuln PYSEC-2026-77 --ignore-vuln GHSA-gr75-jv2w-4656 --ignore-vuln GHSA-6qv9-48xg-fc7f --ignore-vuln GHSA-c67j-w6g6-q2cm --ignore-vuln GHSA-2g6r-c272-w58r --ignore-vuln GHSA-926x-3r5x-gfhw --ignore-vuln GHSA-pjwx-r37v-7724 --ignore-vuln GHSA-f4xh-w4cj-qxq8 --ignore-vuln GHSA-6v7p-g79w-8964 --ignore-vuln GHSA-4xgf-cpjx-pc3j
```

Tracking & Removal
------------------
- Create an issue per ignored advisory to track the upgrade work and owner.
- Remove the CI ignore and the issue only after the fix is merged and CI
  reruns cleanly.

CI parity note
--------------
`local_ci.yml.bat` is intended to mirror the main GitHub Actions `ci.yaml`'s
steps for local convenience, but exact parity depends on environment:

- OS differences: GitHub uses `ubuntu-latest`; `local_ci.yml.bat` runs on
  Windows PowerShell here. Some binaries or behaviors may differ (shell
  semantics, path separators, background process handling).
- Matrix coverage: GitHub runs multiple Python versions and a matrix; local
  script typically runs one interpreter unless you explicitly switch.
- Environment variables and secrets: CI injects different env values; local
  runs may need explicit env stubs (see `local_ci.yml.bat`).

To get the closest parity locally, run the same commands used in CI under an
Ubuntu container (WSL, Docker, or GitHub Codespaces) or run the exact
commands listed in `.github/workflows/ci.yaml` in a matching shell.

If you want, I can:
- (A) Open a feature branch that pins the minimal safe versions for the three
  transitive advisories and run the full CI locally in a container, or
- (B) Create tracked issues for each ignored advisory and add `docs/security.md`
  entries that reference them.
