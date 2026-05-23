@echo off
SETLOCAL EnableDelayedExpansion

echo =======================================================
echo        Enterprise AI Lab Environment Setup
echo =======================================================

cd /d "%~dp0"

:: -------------------------------------------------------
:: 1. Verify uv exists
:: -------------------------------------------------------
where uv >nul 2>nul

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] uv is not installed.
    echo.
    echo Install uv first:
    echo https://docs.astral.sh/uv/getting-started/installation/
    exit /b 1
)

echo [1/5] uv detected.

:: -------------------------------------------------------
:: 2. Remove existing environment
:: -------------------------------------------------------
if exist ".venv" (
    echo [2/5] Removing existing virtual environment...

    if defined VIRTUAL_ENV call deactivate 2>nul

    rmdir /s /q .venv

    if exist ".venv" (
        echo [ERROR] Failed to remove .venv
        exit /b 1
    )
)

:: -------------------------------------------------------
:: 3. Create fresh uv environment
:: -------------------------------------------------------
echo [3/5] Creating fresh Python 3.11 environment...

uv venv --python 3.11

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create virtual environment.
    exit /b %ERRORLEVEL%
)

:: -------------------------------------------------------
:: 4. Sync dependencies from lockfile
:: -------------------------------------------------------
echo [4/5] Installing locked dependencies...

uv sync --all-extras

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Dependency installation failed.
    exit /b %ERRORLEVEL%
)

:: -------------------------------------------------------
:: 5. Install project editable mode
:: -------------------------------------------------------
echo [5/5] Finalizing editable install...

uv pip install -e .

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Editable install failed.
    exit /b %ERRORLEVEL%
)

echo =======================================================
echo   SUCCESS! Environment is fully synchronized.
echo =======================================================

:: -------------------------------------------------------
:: Activate shell
:: -------------------------------------------------------
echo Opening activated shell...

cmd /k .venv\Scripts\activate.bat