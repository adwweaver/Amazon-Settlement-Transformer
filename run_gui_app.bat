@echo off
REM === Amazon Settlement Processor - GUI ===
REM Simple graphical interface for processing settlements

echo.
echo ================================================
echo Starting Amazon Settlement Processor GUI...
echo ================================================
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

REM Run the GUI application
python scripts/gui_app.py

pause



