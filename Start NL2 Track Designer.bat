@echo off
setlocal
title NL2 Track Designer - Setup and Launch
cd /d "%~dp0"

echo ============================================================
echo   NL2 Track Designer - one-click setup and launch
echo ============================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python was not found on this PC. Attempting to install it
    echo automatically using winget (built into Windows 10/11)...
    echo.
    winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% neq 0 (
        echo.
        echo ------------------------------------------------------------
        echo Automatic install did not complete. Please install Python
        echo manually from https://python.org/downloads
        echo IMPORTANT: on the first install screen, check the box
        echo "Add python.exe to PATH" before clicking Install.
        echo Then double-click this file again.
        echo ------------------------------------------------------------
        pause
        exit /b 1
    )
    echo.
    echo Python was installed. Please close this window and double-click
    echo this file again so Windows picks up the new install.
    pause
    exit /b 0
)

if not exist venv (
    echo Setting up the app for the first time - this can take a minute...
    python -m venv venv
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip >nul
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo Something went wrong installing dependencies. Copy the error
        echo above and share it and I can help debug it.
        pause
        exit /b 1
    )
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Launching NL2 Track Designer...
python run_gui.py

if %errorlevel% neq 0 (
    echo.
    echo The app exited with an error. Copy the message above and share
    echo it and I can help debug it.
    pause
)
