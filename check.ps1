# ksef-sync local quality check

$ErrorActionPreference = "Stop"

chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

if (-not (Test-Path ".git")) {
    Write-Host "ERROR: Uruchom check.ps1 z katalogu głównego repozytorium." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Nie znaleziono uv w PATH." -ForegroundColor Red
    exit 1
}

function Run-Step {
    param(
        [string]$Name,
        [string[]]$Command
    )

    Write-Host ""
    Write-Host ("=== {0} ===" -f $Name) -ForegroundColor Cyan
    Write-Host ($Command -join " ")

    & $Command[0] $Command[1..($Command.Count - 1)]

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host ("FAILED: {0} (exit code {1})" -f $Name, $LASTEXITCODE) -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host ""
Write-Host "=== KSEF-SYNC CHECK ===" -ForegroundColor Cyan

Run-Step "Python" @("uv", "run", "python", "--version")
Run-Step "Sync dependencies" @("uv", "sync", "--extra", "dev")
Run-Step "Tests" @("uv", "run", "python", "-m", "pytest")
Run-Step "Ruff" @("uv", "run", "python", "-m", "ruff", "check", ".")
Run-Step "Black" @("uv", "run", "python", "-m", "black", "--check", "main.py", "config.py", "ksef", "tests")
Run-Step "Bandit" @("uv", "run", "python", "-m", "bandit", "-q", "-c", "pyproject.toml", "-r", ".")
Run-Step "Runtime files check" @("uv", "run", "python", "tools/check_runtime_files.py")
Run-Step "Security check" @("uv", "run", "python", "tools/security_check.py", "--redact")

Write-Host ""
Write-Host "OK: wszystkie kontrole przeszły." -ForegroundColor Green
exit 0
