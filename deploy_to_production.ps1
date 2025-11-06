# Deploy Development Changes to Production
# Run this from the GitHub development directory

param(
    [switch]$WhatIf,
    [switch]$Force
)

$devPath = "C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-Settlement-Transformer"
$prodPath = "C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL\etl"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Deploy to Production" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Development: $devPath" -ForegroundColor Yellow
Write-Host "Production:  $prodPath" -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path $prodPath)) {
    Write-Host "ERROR: Production path not found!" -ForegroundColor Red
    exit 1
}

# Files to deploy
$filesToDeploy = @(
    @{Source="scripts\*.py"; Dest="scripts\"; Description="Python ETL scripts"},
    @{Source="config\config.yaml"; Dest="config\"; Description="Configuration file"},
    @{Source="requirements.txt"; Dest=""; Description="Python dependencies"},
    @{Source="README.md"; Dest=""; Description="Documentation"},
    @{Source="create_excel_tracking.py"; Dest=""; Description="Tracking utility"}
)

Write-Host "Files to deploy:" -ForegroundColor Green
foreach ($item in $filesToDeploy) {
    Write-Host "  • $($item.Description)" -ForegroundColor White
}
Write-Host ""

if ($WhatIf) {
    Write-Host "[WHAT-IF MODE] No changes will be made" -ForegroundColor Yellow
    exit 0
}

if (-not $Force) {
    $confirm = Read-Host "Deploy these files to production? (Y/N)"
    if ($confirm -ne 'Y' -and $confirm -ne 'y') {
        Write-Host "Deployment cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""
Write-Host "Deploying..." -ForegroundColor Cyan
Write-Host ""

$deployedCount = 0
foreach ($item in $filesToDeploy) {
    try {
        $sourcePath = Join-Path $devPath $item.Source
        $destPath = Join-Path $prodPath $item.Dest
        
        if (Test-Path $sourcePath) {
            Copy-Item $sourcePath $destPath -Force -ErrorAction Stop
            Write-Host "  ✓ $($item.Description)" -ForegroundColor Green
            $deployedCount++
        } else {
            Write-Host "  ⚠ Skipped: $($item.Description) (not found)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ✗ Failed: $($item.Description) - $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Deployment complete: $deployedCount file(s) deployed" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test production environment" -ForegroundColor White
Write-Host "  2. Restart monitor if running" -ForegroundColor White
Write-Host ""
