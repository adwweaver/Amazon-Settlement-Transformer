@echo off
REM === Amazon Settlement ETL Pipeline Runner ===
REM This batch file provides an easy way to run the ETL pipeline on Windows

echo.
echo ================================================
echo Amazon Settlement ETL Pipeline
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

REM Navigate to the scripts directory
cd /d "%~dp0scripts"

REM Check if required files exist
if not exist "main.py" (
    echo ERROR: main.py not found in scripts directory
    echo Please ensure you're running this from the correct location
    pause
    exit /b 1
)

if not exist "../config/config.yaml" (
    echo ERROR: config.yaml not found
    echo Please ensure the configuration file exists
    pause
    exit /b 1
)

echo Starting ETL Pipeline...
echo.

REM Run the pipeline
python main.py

REM Check if the pipeline completed successfully
if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo ETL Pipeline completed successfully!
    echo ================================================
    echo.
    echo Output files are available in the outputs/ folder
    echo Check logs/ folder for detailed processing logs
) else (
    echo.
    echo ================================================
    echo ETL Pipeline failed with errors
    echo ================================================
    echo.
    echo Please check the log files for error details
)

echo.
echo Press any key to exit...
pause >nul