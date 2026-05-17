param(
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"

Write-Host "=== UV environment setup ===" -ForegroundColor Cyan

$project = Get-Location
$venvPath = Join-Path $project ".venv"

Write-Host "Project directory: $project"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Nie znaleziono uv. Zainstaluj uv: https://docs.astral.sh/uv/" -ForegroundColor Red
    exit 1
}

if ($Rebuild -and (Test-Path $venvPath)) {
    Write-Host "Rebuild requested. Removing existing .venv..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvPath
}

Write-Host "Synchronizuję .venv z pyproject.toml i uv.lock..." -ForegroundColor Green
uv sync --extra dev

if ($LASTEXITCODE -ne 0) {
    Write-Host "UV sync failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Done. Użyj: uv run python main.py --mode full-sync --year 2026 --month 5" -ForegroundColor Cyan
