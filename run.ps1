<#
.SYNOPSIS
    One-Click PowerShell launcher for Canon SELPHY CP1500 Photo Booth Station on Windows.
#>
$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$VenvDir = Join-Path $ScriptDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

# Fast path
if (Test-Path $VenvPython) {
    & $VenvPython (Join-Path $ScriptDir "photobooth.py") @args
    exit $LASTEXITCODE
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " 📸 Canon SELPHY CP1500 Photo Booth Station (Windows)" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[*] First-time launch detected! Setting up environment..." -ForegroundColor Yellow

$pyCmd = (Get-Command py.exe -ErrorAction SilentlyContinue)
if (-not $pyCmd) {
    $pyCmd = (Get-Command python.exe -ErrorAction SilentlyContinue)
}

if ($pyCmd) {
    Write-Host "[*] Creating virtual environment using $($pyCmd.Source)..."
    & $pyCmd.Source -m venv $VenvDir | Out-Null
    if (Test-Path $VenvPython) {
        Write-Host "[*] Installing Pillow..."
        & $VenvPython -m pip install --quiet Pillow
    }
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "[*] Setting up portable runner (uv)..."
    try {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression | Out-Null
        $env:Path = "$env:USERPROFILE\.cargo\bin;$env:USERPROFILE\.local\bin;" + $env:Path
        & uv venv $VenvDir --quiet
        & uv pip install --quiet --python $VenvPython Pillow
    } catch {
        Write-Host "[ERROR] Could not automatically configure Python environment." -ForegroundColor Red
        Write-Host "Please install Python 3.10+ from https://www.python.org/downloads/ (check 'Add to PATH')."
        Read-Host "Press Enter to exit..."
        exit 1
    }
}

if (Test-Path $VenvPython) {
    Write-Host "[OK] Setup complete! Launching..." -ForegroundColor Green
    & $VenvPython (Join-Path $ScriptDir "photobooth.py") @args
} else {
    Write-Host "[ERROR] Virtual environment could not be created." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}
