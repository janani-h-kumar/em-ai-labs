@echo off
SETLOCAL EnableDelayedExpansion

echo =======================================================
echo         Running Quality Assurance Pipeline
echo =======================================================

:: Resolve the absolute root directory of your project space
SET "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

:: =======================================================
:: 1. LOCATE RUFF
:: =======================================================

:: Check if ruff is already available in the active PATH environment
where ruff >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    SET "RUFF_CMD=ruff"
) else (
    :: Fallback to local disk path if not active
    if exist "%PROJECT_ROOT%.venv\Scripts\ruff.exe" (
        SET "RUFF_CMD=\"%PROJECT_ROOT%.venv\Scripts\ruff.exe\""
    ) else (
        echo [ERROR] Ruff linter could not be found in active PATH or local .venv.
        echo         Please run setup.bat to configure your environment.
        exit /b 1
    )
)

:: =======================================================
:: 2. LOCATE MYPY
:: =======================================================

:: Check if mypy is already available in the active PATH environment
where mypy >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    SET "MYPY_CMD=mypy"
) else (
    :: Fallback to local disk path if not active
    if exist "%PROJECT_ROOT%.venv\Scripts\mypy.exe" (
        SET "MYPY_CMD=\"%PROJECT_ROOT%.venv\Scripts\mypy.exe\""
    ) else (
        echo [ERROR] Mypy type checker could not be found in active PATH or local .venv.
        echo         Please install mypy or run setup.bat.
        exit /b 1
    )
)

:: =======================================================
:: 3. LOCATE PYTEST
:: =======================================================

:: Check if pytest is already available in the active PATH environment
where pytest >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    SET "PYTEST_CMD=pytest"
) else (
    :: Fallback to local disk path if not active
    if exist "%PROJECT_ROOT%.venv\Scripts\pytest.exe" (
        SET "PYTEST_CMD=\"%PROJECT_ROOT%.venv\Scripts\pytest.exe\""
    ) else (
        echo [ERROR] Pytest framework could not be found in active PATH or local .venv.
        echo         Please run setup.bat to configure your environment.
        exit /b 1
    )
)

:: =======================================================
:: EXECUTION PHASE
:: =======================================================

:: Phase 1: Linting and Code Style Checks
echo [1/3] Executing Ruff Linter...
echo -------------------------------------------------------
!RUFF_CMD! check . --fix
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] Code quality checks failed. Please fix the lint errors above.
    exit /b %ERRORLEVEL%
)
echo [PASS] Code quality checks passed cleanly.
echo.

:: Phase 2: Static Type Checking
::echo [2/3] Executing Mypy Type Checks...
::echo -------------------------------------------------------
::!MYPY_CMD! .
::if %ERRORLEVEL% NEQ 0 (
::    echo.
::    echo [FAIL] Mypy type checks failed.
::    exit /b %ERRORLEVEL%
::)
::echo [PASS] Mypy type checks passed.
::echo.

:: Phase 3: Automated Unit and Integration Testing
echo [3/3] Executing Pytest Framework...
echo -------------------------------------------------------
!PYTEST_CMD!
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] One or more unit tests failed.
    exit /b %ERRORLEVEL%
)
echo [PASS] All test cases executed successfully.

echo =======================================================
echo   SUCCESS! Everything is green. Ready to commit.
echo =======================================================

ENDLOCAL