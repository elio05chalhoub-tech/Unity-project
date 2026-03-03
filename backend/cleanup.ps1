# cleanup.ps1
$ErrorActionPreference = "Continue"

Write-Host "Starting environment purge..." -ForegroundColor Cyan

$BackendDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$DirectoriesToRemove = @(
    "HunyuanWorld-1.0",
    "tsr",
    "Real-ESRGAN",
    ".venv",
    "venv"
)

foreach ($dir in $DirectoriesToRemove) {
    $targetPath = Join-Path $BackendDir $dir
    if (Test-Path $targetPath) {
        Write-Host "Removing: $targetPath" -ForegroundColor Yellow
        Remove-Item -Recurse -Force $targetPath
        Write-Host "Deleted: $targetPath" -ForegroundColor Green
    }
    else {
        Write-Host "Not found (skipping): $targetPath" -ForegroundColor DarkGray
    }
}

Write-Host "Cleanup complete!" -ForegroundColor Cyan
