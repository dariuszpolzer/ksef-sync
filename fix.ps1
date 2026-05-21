# ============================================
# FIX.PS1 — autoformat + lint fix
# Projekt: ksef-sync
# Python: 3.13 / uv
# ============================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== KSEF-SYNC AUTO FIX ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".git")) {
    Write-Host "ERROR: Uruchom skrypt z katalogu głównego repozytorium." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Nie znaleziono uv. Zainstaluj uv i uruchom: uv sync --extra dev" -ForegroundColor Red
    exit 1
}

$targets = @(
    "main.py",
    "config.py",
    "ksef",
    "tests"
)

$existingTargets = @()
foreach ($target in $targets) {
    if (Test-Path $target) {
        $existingTargets += $target
    }
}

if ($existingTargets.Count -eq 0) {
    Write-Host "ERROR: Nie znaleziono plików do poprawy." -ForegroundColor Red
    exit 1
}

Write-Host "Python:" -ForegroundColor Cyan
uv run python --version

Write-Host ""
Write-Host "Targets:" -ForegroundColor Cyan
$existingTargets | ForEach-Object { Write-Host " - $_" }

Write-Host ""
Write-Host "=== RUFF FIX ===" -ForegroundColor Cyan
uv sync --extra dev
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nUV SYNC FAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}

uv run ruff check --fix @existingTargets
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nRUFF FIX FAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "=== BLACK FORMAT ===" -ForegroundColor Cyan
uv run black @existingTargets
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nBLACK FORMAT FAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "=== RUFF CHECK AFTER FIX ===" -ForegroundColor Cyan
uv run ruff check @existingTargets
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nRUFF CHECK FAILED AFTER FIX" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Gotowe. Teraz uruchom: .\check.ps1" -ForegroundColor Green
Write-Host ""

exit 0
