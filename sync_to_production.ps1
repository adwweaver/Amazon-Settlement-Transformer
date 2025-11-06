# Auto-Sync Development to Production
# Run this in a separate PowerShell window to keep both environments in sync

param(
    [switch]$Once,
    [int]$IntervalSeconds = 5
)

$devPath = "C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-Settlement-Transformer"
$prodPath = "C:\Users\User\Touchstone Brands\BrackishCo - Documents\Sharepoint_Public\Amazon-ETL\etl"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Auto-Sync: Development → Production" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Development: $devPath" -ForegroundColor Yellow
Write-Host "Production:  $prodPath" -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path $prodPath)) {
    Write-Host "ERROR: Production path not found!" -ForegroundColor Red
    exit 1
}

# Files to monitor and sync
$syncPaths = @(
    @{Pattern="scripts\*.py"; Dest="scripts\"},
    @{Pattern="config\config.yaml"; Dest="config\"},
    @{Pattern="create_excel_tracking.py"; Dest=""}
)

function Sync-Files {
    $changes = 0
    
    foreach ($item in $syncPaths) {
        $sourcePattern = Join-Path $devPath $item.Pattern
        $sourceFiles = Get-ChildItem $sourcePattern -File -ErrorAction SilentlyContinue
        
        foreach ($file in $sourceFiles) {
            $destPath = Join-Path $prodPath $item.Dest
            $destFile = Join-Path $destPath $file.Name
            
            # Check if file needs updating
            if (-not (Test-Path $destFile) -or 
                $file.LastWriteTime -gt (Get-Item $destFile).LastWriteTime) {
                
                Copy-Item $file.FullName $destFile -Force
                Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Synced: $($file.Name)" -ForegroundColor Green
                $changes++
            }
        }
    }
    
    return $changes
}

if ($Once) {
    Write-Host "Performing one-time sync..." -ForegroundColor Cyan
    $synced = Sync-Files
    Write-Host ""
    Write-Host "Sync complete: $synced file(s) updated" -ForegroundColor Green
    exit 0
}

Write-Host "Monitoring for changes (checking every $IntervalSeconds seconds)..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

$lastSync = Get-Date

while ($true) {
    $changes = Sync-Files
    
    if ($changes -gt 0) {
        $lastSync = Get-Date
        Write-Host "  → Total changes synced: $changes" -ForegroundColor Cyan
    }
    
    Start-Sleep -Seconds $IntervalSeconds
}
