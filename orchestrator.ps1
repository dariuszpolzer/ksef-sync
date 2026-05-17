param(
    [int]$Year = 0,
    [int]$Month = 0,
    [switch]$DryRun,
    [switch]$SkipSync,
    [switch]$SkipJpk,
    [switch]$SkipTaxApp
)

chcp 65001 | Out-Null

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

if ($Year -eq 0 -or $Month -eq 0) {
    $prevMonth = (Get-Date).AddMonths(-1)
    $Year = [int]$prevMonth.ToString("yyyy")
    $Month = [int]$prevMonth.ToString("MM")
}

if ($Month -lt 1 -or $Month -gt 12) {
    throw ("Nieprawidłowy miesiąc: {0}" -f $Month)
}

$period = "{0}-{1:00}" -f $Year, $Month
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

$root = "C:\Users\dpolz\Documents"

$ksefSyncDir = "$root\ksef-sync"
$ksef2jpkDir = "$root\ksef-jpk"
$taxAppDir = "$root\tax-app"

$logDir = "$root\logs"
$reportDir = "$root\reports\$period\$timestamp"
$logFile = "$logDir\monthly_${period}_${timestamp}.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

function Write-Log {
    param(
        [string]$Message
    )

    Add-Content -Path $logFile -Value $Message -Encoding UTF8
}

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Name
    )

    if (-not (Test-Path $Path)) {
        throw ("Brak {0}: {1}" -f $Name, $Path)
    }
}

function Assert-CommandExists {
    param(
        [string]$CommandName
    )

    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw ("Brak wymaganego polecenia w PATH: {0}" -f $CommandName)
    }
}

function Run-Step {
    param(
        [string]$Name,
        [string]$WorkingDir,
        [string]$Command
    )

    Write-Host ""
    Write-Host ("=== {0} ===" -f $Name)
    Write-Host ("Path: {0}" -f $WorkingDir)
    Write-Host ("Command: {0}" -f $Command)

    Write-Log ""
    Write-Log ("=== {0} ===" -f $Name)
    Write-Log ("Path: {0}" -f $WorkingDir)
    Write-Log ("Command: {0}" -f $Command)

    Assert-PathExists -Path $WorkingDir -Name "katalog roboczy"

    if ($DryRun) {
        Write-Host "[DRY RUN] Pomijam wykonanie."
        Write-Log "[DRY RUN] Pomijam wykonanie."
        return
    }

    Push-Location $WorkingDir

    try {
        Invoke-Expression $Command 2>&1 |
            Tee-Object -FilePath $logFile -Append

        if ($LASTEXITCODE -ne 0) {
            throw ("{0} zakończony błędem: exit code {1}" -f $Name, $LASTEXITCODE)
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host "=== ORCHESTRATOR ROZLICZENIA ==="
Write-Host ("Okres: {0}" -f $period)
Write-Host ("Log: {0}" -f $logFile)
Write-Host ("Raporty: {0}" -f $reportDir)

Write-Log "=== ORCHESTRATOR ROZLICZENIA ==="
Write-Log ("Okres: {0}" -f $period)
Write-Log ("Start: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Log ("Raporty: {0}" -f $reportDir)

try {
    Assert-CommandExists -CommandName "uv"

    if (-not $SkipSync) {
        Assert-PathExists -Path $ksefSyncDir -Name "katalog ksef-sync"
    }

    if (-not $SkipJpk) {
        Assert-PathExists -Path $ksef2jpkDir -Name "katalog ksef-jpk"
    }

    if (-not $SkipTaxApp) {
        Assert-PathExists -Path $taxAppDir -Name "katalog tax-app"
    }

    if (-not $SkipSync) {
        Run-Step `
            -Name "KSeF Sync" `
            -WorkingDir $ksefSyncDir `
            -Command "uv run python main.py --mode full-sync --year $Year --month $Month"
    }
    else {
        Write-Host ""
        Write-Host "=== KSeF Sync ==="
        Write-Host "[SKIP] Pominięto synchronizację."
        Write-Log "KSeF Sync: SKIPPED"
    }

    if (-not $SkipJpk) {
        Run-Step `
            -Name "KSeF to JPK" `
            -WorkingDir $ksef2jpkDir `
            -Command "uv run python -m ksef2jpk.main --year $Year --month $Month"
    }
    else {
        Write-Host ""
        Write-Host "=== KSeF → JPK ==="
        Write-Host "[SKIP] Pominięto generowanie JPK."
        Write-Log "KSeF to JPK: SKIPPED"
    }

    if (-not $SkipTaxApp) {
        Run-Step `
            -Name "Tax App" `
            -WorkingDir $taxAppDir `
            -Command "uv run python main.py --year $Year --month $Month --out-dir `"$reportDir`""
    }
    else {
        Write-Host ""
        Write-Host "=== Tax App ==="
        Write-Host "[SKIP] Pominięto tax-app."
        Write-Log "Tax App: SKIPPED"
    }

    Write-Log "Status: SUCCESS"
    Write-Log ("Koniec: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

    Write-Host ""
    Write-Host "=== GOTOWE ==="
    Write-Host ("Okres: {0}" -f $period)
    Write-Host ("Raporty: {0}" -f $reportDir)
    Write-Host ("Log: {0}" -f $logFile)

    exit 0
}
catch {
    Write-Log "Status: FAILED"
    Write-Log ("Błąd: {0}" -f $_.Exception.Message)
    Write-Log ("Koniec: {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

    Write-Host ""
    Write-Host "=== BŁĄD ==="
    Write-Host $_.Exception.Message
    Write-Host ("Log: {0}" -f $logFile)

    exit 1
}
