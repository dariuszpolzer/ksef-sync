param(
    [switch]$Force,
    [switch]$Rebuild,
    [string]$PythonPath = "python"
)

Write-Host "=== Python venv manager ===" -ForegroundColor Cyan

$project = Get-Location
$venvPath = Join-Path $project "venv"
$activatePath = Join-Path $venvPath "Scripts\Activate.ps1"
$reqFile = Join-Path $project "requirements.txt"

Write-Host "Project directory: $project"

# Remove venv completely
if ($Rebuild -and (Test-Path $venvPath)) {
    Write-Host "Rebuild requested. Removing existing venv..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvPath
}

# Create venv
if (-not (Test-Path $venvPath) -or $Force) {

    if ($Force -and (Test-Path $venvPath)) {
        Write-Host "Force enabled. Removing existing venv..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $venvPath
    }

    Write-Host "Creating venv using: $PythonPath" -ForegroundColor Green

    & $PythonPath -m venv venv

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to create venv." -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "venv already exists." -ForegroundColor Yellow
}

# Activate venv
if (Test-Path $activatePath) {
    Write-Host "Activating venv..." -ForegroundColor Green
    . $activatePath
}
else {
    Write-Host "ERROR: Activation script not found." -ForegroundColor Red
    exit 1
}

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
if (Test-Path $reqFile) {
    Write-Host "Installing dependencies..." -ForegroundColor Green
    python -m pip install -r $reqFile
}
else {
    Write-Host "requirements.txt not found." -ForegroundColor Yellow
}

Write-Host "Done. venv is active." -ForegroundColor Cyan