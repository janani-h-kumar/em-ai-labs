@echo off
SETLOCAL EnableDelayedExpansion

echo =======================================================
echo     Enterprise AI Lab Environment Initialization
echo =======================================================

cd /d "%~dp0"

:: 1. Read .env file to discover the Environment Mode
set "APP_ENV=dev"  :: Default fallback if not found
if exist ".env" (
    for /f "tokens=1,2 delims==" %%A in (.env) do (
        :: Strip out spaces around the key name to be safe
        set "key=%%A"
        set "key=!key: =!"
        if /i "!key!"=="APP_ENV" (
            set "val=%%B"
            :: Strip out spaces/quotes from the value
            set "val=!val: =!"
            set "val=!val:"=!"
            set "val=!val:'=!"
            set "APP_ENV=!val!"
        )
    )
    echo [*] Detected environment from .env: !APP_ENV!
) else (
    echo [WARNING] No .env file found at root. Defaulting to: !APP_ENV!
)

:: 2. Clean up existing virtual environment
if exist ".venv" (
    echo [1/4] Found existing environment. Cleaning up old .venv...
    if defined VIRTUAL_ENV call deactivate 2>nul
    rmdir /s /q .venv
    if exist ".venv" (
        echo [ERROR] Failed to delete old .venv folder. Ensure no IDE is locking it.
        exit /b 1
    )
    echo       Clean-up complete.
) else (
    echo [1/4] No existing environment found. Skipping clean-up.
)

:: 3. Create fresh local environment sandbox
echo [2/4] Creating a pristine virtual environment...
py -3.11 -m venv .venv
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to create virtual environment.
    exit /b %ERRORLEVEL%
)

:: 4. Install dependencies based on .env layout choice
echo [3/4] Installing dependencies for mode: !APP_ENV! ...
.venv\Scripts\python.exe -m pip install --upgrade pip

if /i "!APP_ENV!"=="dev" (
    :: In development, we typically want both production and dev tools
    if exist "requirements\prod.txt" .venv\Scripts\python.exe -m pip install -r requirements\prod.txt
    if exist "requirements\dev.txt" .venv\Scripts\python.exe -m pip install -r requirements\dev.txt
) else (
    :: Production only installs target dependencies
    if exist "requirements\prod.txt" (
        .venv\Scripts\python.exe -m pip install -r requirements\prod.txt
    ) else (
        echo [ERROR] requirements\prod.txt not found.
        exit /b 1
    )
)
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies.
    exit /b %ERRORLEVEL%
)

:: 5. Link local layout
echo [4/4] Linking local 'src' directory in editable mode...
.venv\Scripts\python.exe -m pip install -e .
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install project in editable mode.
    exit /b %ERRORLEVEL%
)

echo =======================================================
echo   SUCCESS! Environment built (!APP_ENV! mode).
echo =======================================================

:: End local environment scope but pass target mode variable to out-of-block trick
set "FINAL_MODE=!APP_ENV!"
ENDLOCAL

echo %cmdcmdline% | findstr /i /c:"/c" >nul
if %ERRORLEVEL% EQU 0 (
    echo Environment is ready. Opening an activated shell for you...
    cmd /k .venv\Scripts\activate.bat
) else (
    echo Activating environment in your current terminal session...
    call .venv\Scripts\activate.bat
)