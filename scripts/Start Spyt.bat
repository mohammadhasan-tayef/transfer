@echo off
title spyt - Spotify to YouTube Music
set "ROOT=%~dp0.."
cd /d "%ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo First time? Running setup...
    call "%~dp0\install.bat"
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m spyt
set EXITCODE=%ERRORLEVEL%

echo.
if %EXITCODE% neq 0 (
    echo Something went wrong. See the message above.
) else (
    echo All done. You can close this window.
)
echo.
pause
exit /b %EXITCODE%
