@echo off
REM === Deploy to GitHub - Simple Script ===
REM This script commits and pushes the web app to GitHub

echo.
echo ================================================
echo Deploy to GitHub - Amazon Settlement Processor
echo ================================================
echo.

REM Check if Git is available
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Git is not installed or not in PATH
    echo Please install Git from: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Step 1: Checking Git status...
echo.
git status --short

echo.
echo ================================================
echo Files ready to commit:
echo   - scripts/web_app.py (Streamlit web app)
echo   - scripts/deploy_to_sharepoint.py (Deployment helper)
echo   - requirements.txt (Updated dependencies)
echo   - .streamlit/config.toml (Streamlit config)
echo ================================================
echo.

REM Ask for confirmation
set /p confirm="Do you want to commit and push these files? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo.
    echo Deployment cancelled.
    pause
    exit /b 0
)

echo.
echo Step 2: Committing files...
git commit -m "Add Streamlit web app for SharePoint deployment"

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Commit failed. Check the error message above.
    pause
    exit /b 1
)

echo.
echo Step 3: Pushing to GitHub...
git push origin main

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Push failed. Check the error message above.
    echo.
    echo Common issues:
    echo   - Not authenticated with GitHub (run: git config --global user.name "Your Name")
    echo   - No internet connection
    echo   - Branch name might be 'master' instead of 'main' (try: git push origin master)
    pause
    exit /b 1
)

echo.
echo ================================================
echo ✅ SUCCESS! Files pushed to GitHub
echo ================================================
echo.
echo Next steps:
echo   1. Go to: https://share.streamlit.io
echo   2. Sign in with GitHub
echo   3. Click "New app"
echo   4. Select repository: Amazon-Settlement-Transformer
echo   5. Main file: scripts/web_app.py
echo   6. Click "Deploy"
echo.
echo See QUICK_DEPLOY_TO_SHAREPOINT.md for complete guide
echo.
pause



