@echo off
:: Build a standalone Nation Forge.exe game launcher via PyInstaller.
title Building Nation Forge.exe

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found on your PATH.
    pause
    exit /b 1
)

cd /d "%~dp0governance_sim"

echo Installing/checking dependencies...
python -m pip install -r requirements.txt pyinstaller
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Building executable...
pyinstaller --onefile --name NationForge --console main.py
if %errorlevel% neq 0 (
    echo [ERROR] Build failed. See output above.
    pause
    exit /b 1
)

copy /Y "dist\NationForge.exe" "..\Nation Forge.exe" >nul
echo.
echo Build complete: "Nation Forge.exe" is ready in the project root.
pause
