@echo off
REM === ETL Pipeline Test Runner ===
REM This batch file runs the validation and testing suite

echo.
echo ================================================
echo ETL Pipeline - Running Tests and Validation
echo ================================================
echo.

REM Navigate to the scripts directory
cd /d "%~dp0scripts"

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo Running unit tests and validation...
echo.

REM Run the validation tests
python validate.py

REM Check results
if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo All tests passed successfully!
    echo ================================================
) else (
    echo.
    echo ================================================
    echo Some tests failed - please review the output
    echo ================================================
)

echo.
echo Press any key to exit...
pause >nul