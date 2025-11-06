@echo off
REM === Amazon Settlement Processor - Web App ===
REM This starts the Streamlit web application
REM Access it at: http://localhost:8501

echo.
echo ================================================
echo Amazon Settlement Processor - Web App
echo ================================================
echo.
echo Starting Streamlit web application...
echo.
echo The app will open in your browser at:
echo   http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

REM Check if Streamlit is installed
python -c "import streamlit" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Installing required package: streamlit
    pip install streamlit
    echo.
)

REM Navigate to project directory
cd /d "%~dp0"

REM Run Streamlit app
streamlit run scripts/web_app.py

pause



