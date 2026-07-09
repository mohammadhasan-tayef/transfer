@echo off
title spyt - pack files for home
set "ROOT=%~dp0.."
cd /d "%ROOT%"

set PACK=home-pack
set SRC=.spyt

echo.
echo ========================================
echo   Packing your migration data for home
echo ========================================
echo.

if not exist "%SRC%\backup.json" (
    echo ERROR: %SRC%\backup.json not found.
    echo Import Exportify first, or finish filter-backup.
    pause
    exit /b 1
)

if exist "%PACK%" rmdir /s /q "%PACK%"
mkdir "%PACK%"
mkdir "%PACK%\.spyt"

copy /y "%SRC%\backup.json" "%PACK%\.spyt\backup.json" >nul
echo   [ok] backup.json

if exist "%SRC%\backup.json.bak" (
    copy /y "%SRC%\backup.json.bak" "%PACK%\.spyt\backup.json.bak" >nul
    echo   [ok] backup.json.bak
)

if exist "%SRC%\keep_playlists.txt" (
    copy /y "%SRC%\keep_playlists.txt" "%PACK%\.spyt\keep_playlists.txt" >nul
    echo   [ok] keep_playlists.txt
)

if exist "%SRC%\unmatched.json" (
    copy /y "%SRC%\unmatched.json" "%PACK%\.spyt\unmatched.json" >nul
    echo   [ok] unmatched.json
)

if exist "MY_MIGRATION.md" (
    copy /y "MY_MIGRATION.md" "%PACK%\MY_MIGRATION.md" >nul
    echo   [ok] MY_MIGRATION.md
) else (
    echo   [skip] MY_MIGRATION.md — fill it in first at project root
)

(
echo Copy this entire "%PACK%" folder to USB or cloud.
echo.
echo At home:
echo   1. Clone or copy the spyt project
echo   2. Copy home-pack\.spyt\* into your project\.spyt\
echo   3. Run scripts\install.bat
echo   4. python -m spyt setup-ytmusic
echo   5. python -m spyt migrate-all --from-backup
echo.
echo See MY_MIGRATION.md for full checklist.
) > "%PACK%\READ_ME_FIRST.txt"

echo.
echo Done! Folder ready:
echo   %cd%\%PACK%
echo.
echo Copy the whole "%PACK%" folder to take home.
echo Do NOT upload it to GitHub.
echo.
pause
