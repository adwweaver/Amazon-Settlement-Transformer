@echo off
REM Start SharePoint-integrated Settlement File Watcher
REM This monitors the synced SharePoint folder for new settlement files

cd /d "%~dp0"

echo ========================================
echo SharePoint Settlement File Watcher
echo ========================================
echo.
echo Starting watchdog service...
echo This will monitor the SharePoint synced folder for new settlement files.
echo Press Ctrl+C to stop.
echo.

python scripts/sharepoint_watchdog.py

pause

