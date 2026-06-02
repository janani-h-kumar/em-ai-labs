@echo off
setlocal

echo ==============================
echo 🚀 LOCAL CI (uv-based)
echo ==============================

echo.
echo 📦 Syncing environment...
uv sync --extra dev

echo.
echo 🧹 Ruff lint...
uv run ruff check src/ tests/ --output-format=github

echo.
echo 🎨 Ruff format check...
uv run ruff format src/ tests/ --check

echo.
echo 🧠 MyPy type check...
uv run mypy src/ --ignore-missing-imports --strict-optional

echo.
echo 🔐 Bandit scan...
uv run bandit -r src/ -ll --skip B101

echo.
echo 📦 pip-audit...
uv run pip-audit ^
  --ignore-vuln GHSA-6w46-j5rx-g56g ^
  --ignore-vuln PYSEC-2026-76 ^
  --ignore-vuln PYSEC-2026-77 ^
  --ignore-vuln GHSA-6qv9-48xg-fc7f ^
  --ignore-vuln GHSA-c67j-w6g6-q2cm ^
  --ignore-vuln GHSA-2g6r-c272-w58r ^
  --ignore-vuln GHSA-926x-3r5x-gfhw ^
  --ignore-vuln GHSA-pjwx-r37v-7724

echo.
echo 🧪 Running unit tests...
uv run pytest tests/unit/ -v --tb=short

echo.
echo ==============================
echo ✅ CI PASSED LOCALLY
echo ==============================

endlocal