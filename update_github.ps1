# update-github.ps1
# Czyszczenie projektu ksef-sync przed wysyłką na GitHub

Write-Host ""
Write-Host "=== PREPARE KSEF-SYNC FOR GITHUB ===" -ForegroundColor Cyan
Write-Host ""

# Bezpiecznik: upewnij się, że skrypt działa z katalogu projektu
if (!(Test-Path ".git")) {
    Write-Host "Blad: uruchom skrypt z katalogu glownego repozytorium Git." -ForegroundColor Red
    exit 1
}

# Usunięcie virtualenv
if (Test-Path ".\venv") {
    Write-Host "Usuwanie venv..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".\venv"
}

if (Test-Path ".\.venv") {
    Write-Host "Usuwanie .venv..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force ".\.venv"
}

# Usunięcie cache Python
Write-Host "Usuwanie __pycache__..." -ForegroundColor Yellow
Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# Usunięcie plików pyc
Write-Host "Usuwanie *.pyc..." -ForegroundColor Yellow
Get-ChildItem -Recurse -Include *.pyc -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

# Katalogi robocze/cache/runtime
$dirs = @(
    "output",
    "outputs",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "batches",
    "logs",
    "exports"
)

foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "Usuwanie $dir ..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $dir
    }
}

# UWAGA:
# auth/ i keys/ zawierają dane wrażliwe.
# Nie usuwam ich automatycznie, żeby przypadkiem nie skasować kluczy/tokenów.
# Muszą być jednak wpisane do .gitignore.

Write-Host ""
Write-Host "Sprawdz .gitignore. Powinien zawierac minimum:" -ForegroundColor Cyan
Write-Host ".env"
Write-Host "keys/"
Write-Host "auth/"
Write-Host "batches/"
Write-Host "logs/"
Write-Host "exports/"
Write-Host "venv/"
Write-Host ".venv/"
Write-Host ""

Write-Host "Status Git:" -ForegroundColor Cyan
git status --short

Write-Host ""
Write-Host "Gotowe. Sprawdz powyzszy status przed wykonaniem: git add ." -ForegroundColor Green
Write-Host ""
