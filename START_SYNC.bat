@echo off
echo ========================================
echo Starting Auto-Sync to Production
echo ========================================
echo.
echo This will automatically sync changes from:
echo   Development: C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-Settlement-Transformer
echo   Production:  SharePoint Amazon-ETL\etl
echo.
echo Keep this window open while developing.
echo Press Ctrl+C to stop syncing.
echo.
pause

cd /d "C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-Settlement-Transformer"
powershell -NoExit -ExecutionPolicy Bypass -File ".\sync_to_production.ps1"
