@echo off
setlocal
title Canon SELPHY CP1500 Photo Booth Station

cd /d "%~dp0"

echo ========================================================
echo  Canon SELPHY CP1500 Photo Booth Station (Windows)
echo ========================================================
echo.

where py >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXE=py -3"
    goto :RUN
)

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXE=python"
    goto :RUN
)

echo [ERROR] Python was not found on your system PATH!
echo Please install Python 3.10+ from python.org or Microsoft Store and check "Add Python to PATH".
echo.
pause
exit /b 1

:RUN
%PYTHON_EXE% photobooth.py %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo Application exited with error code %ERRORLEVEL%.
    pause
)

