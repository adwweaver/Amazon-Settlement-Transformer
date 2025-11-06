@echo off
REM === Amazon Settlement Auto-Processor ===
REM This script monitors the settlement folder and processes new files automatically

echo.
echo ================================================
echo Amazon Settlement Auto-Processor
echo ================================================
echo.
echo This will monitor the settlement folder and automatically
echo process any new .txt files that are added.
echo.
echo Press Ctrl+C to stop
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

REM Navigate to project directory
cd /d "%~dp0"

REM Check if watchdog is installed
python -c "import watchdog" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Installing required package: watchdog
    pip install watchdog
    echo.
)

REM Run the file watcher
python scripts/watchdog.py

pause



