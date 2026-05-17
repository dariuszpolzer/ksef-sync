# ============================================
# CHECK.PS1 — testy + lint + format + security
# Projekt: ksef-sync
# Python: 3.13 / uv
# ============================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== KSEF-SYNC QUALITY CHECK ===" -ForegroundColor Cyan
Write-Host ""

# Uruchamiaj z katalogu głównego repo
if (-not (Test-Path ".git")) {
    Write-Host "ERROR: Uruchom skrypt z katalogu głównego repozytorium." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Nie znaleziono uv. Zainstaluj uv i uruchom: uv sync --extra dev" -ForegroundColor Red
    exit 1
}

Write-Host "=== UV SYNC ===" -ForegroundColor Cyan
uv sync --extra dev
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nUV SYNC FAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}

# Główne pliki/katalogi projektu
$lintTargets = @(
    "main.py",
    "config.py",
    "ksef",
    "tools"
)

# Tylko istniejące targety
$existingLintTargets = @()
foreach ($target in $lintTargets) {
    if (Test-Path $target) {
        $existingLintTargets += $target
    }
}

if ($existingLintTargets.Count -eq 0) {
    Write-Host "ERROR: Nie znaleziono plików źródłowych do sprawdzenia." -ForegroundColor Red
    exit 1
}

# Testy — opcjonalne, bo katalog tests może jeszcze nie istnieć
$hasTests = Test-Path "tests"

Write-Host "Python:" -ForegroundColor Cyan
uv run python --version

Write-Host ""
Write-Host "Targets:" -ForegroundColor Cyan
$existingLintTargets | ForEach-Object { Write-Host " - $_" }

# PYTEST
if ($hasTests) {
    Write-Host ""
    Write-Host "=== PYTEST ===" -ForegroundColor Cyan
    uv run pytest -v
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nPYTEST FAILED" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}
else {
    Write-Host ""
    Write-Host "=== PYTEST ===" -ForegroundColor Cyan
    Write-Host "Brak katalogu tests/ — pomijam testy." -ForegroundColor Yellow
}

# RUFF
Write-Host ""
Write-Host "=== RUFF ===" -ForegroundColor Cyan
uv run ruff check @existingLintTargets
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nRUFF FAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}

# BLACK
Write-Host ""
Write-Host "=== BLACK CHECK ===" -ForegroundColor Cyan
uv run black --check @existingLintTargets
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nBLACK FAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}

# BANDIT
Write-Host ""
Write-Host "=== BANDIT ===" -ForegroundColor Cyan
uv run bandit -r ksef
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nBANDIT FAILED" -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "Wszystkie kontrole zakończone sukcesem." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""

exit 0
