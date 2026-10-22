<#
.SYNOPSIS
    Quick PowerShell launcher for Canon SELPHY CP1500 Photo Booth Station on Windows.
#>
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$python = (Get-Command py.exe -ErrorAction SilentlyContinue)
if (-not $python) {
    $python = (Get-Command python.exe -ErrorAction SilentlyContinue)
}

if (-not $python) {
    Write-Host "[ERROR] Python was not found on your system PATH." -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/ (check 'Add to PATH')."
    Read-Host "Press Enter to exit..."
    exit 1
}

& $python.Source photobooth.py $args

