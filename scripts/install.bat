@echo off
title spyt - one-time setup
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo.
echo ========================================
echo   spyt - one-time setup
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo Python is not installed.
    echo.
    echo Download Python from https://www.python.org/downloads/
    echo During install, check "Add python.exe to PATH".
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Installing spyt...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -e . -q
if errorlevel 1 (
    echo Installation failed.
    pause
    exit /b 1
)

echo.
echo Setup complete!
echo.
echo Next: double-click "scripts\Start Spyt.bat" to begin.
echo.
pause
