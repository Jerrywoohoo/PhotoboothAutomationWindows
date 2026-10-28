@echo off
setlocal enabledelayedexpansion
title Canon SELPHY CP1500 Photo Booth Station

cd /d "%~dp0"

set "VENV_DIR=%~dp0.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

:: 1. Fast Path: If virtual environment exists, launch immediately!
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" "%~dp0photobooth.py" %*
    goto :END
)

echo ========================================================
echo  Canon SELPHY CP1500 Photo Booth Station (Windows)
echo ========================================================
echo.
echo [*] First-time launch detected! Setting up environment...
echo [*] This only takes a few seconds and happens once...
echo.

:: 2. Find system Python
set "SYS_PYTHON="
where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "SYS_PYTHON=py -3"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "SYS_PYTHON=python"
    )
)

if defined SYS_PYTHON (
    echo [*] Creating isolated environment with !SYS_PYTHON!...
    !SYS_PYTHON! -m venv "%VENV_DIR%" >nul 2>nul
    if exist "%VENV_PYTHON%" (
        echo [*] Installing required image library (Pillow)...
        "%VENV_PYTHON%" -m pip install --quiet Pillow
        goto :LAUNCH
    )
)

:: 3. Fallback: Standalone UV runner for Windows
echo [*] Using portable installer runner...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" >nul 2>nul
set "PATH=%USERPROFILE%\.cargo\bin;%USERPROFILE%\.local\bin;%PATH%"

where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    uv venv "%VENV_DIR%" --quiet
    uv pip install --quiet --python "%VENV_PYTHON%" Pillow
    goto :LAUNCH
)

echo.
echo [ERROR] Could not set up Python environment automatically.
echo Please install Python 3.10+ from https://www.python.org/downloads/
echo (Make sure to check "Add Python to PATH" during installation!)
echo.
pause
exit /b 1

:LAUNCH
if exist "%VENV_PYTHON%" (
    echo [OK] Setup complete! Launching Photo Booth...
    echo.
    "%VENV_PYTHON%" "%~dp0photobooth.py" %*
) else (
    echo [ERROR] Installation failed.
    pause
    exit /b 1
)

:END
if %ERRORLEVEL% neq 0 (
    echo.
    echo Application exited with code %ERRORLEVEL%.
    pause
)
