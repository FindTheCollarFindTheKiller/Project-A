@echo off
chcp 65001 >nul
title Nation Forge — Country Governance Simulation

cd /d "%~dp0governance_sim"

:: ── Check Python ─────────────────────────────────────────────────────────────
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python was not found on your PATH.
    echo.
    echo  Install Python 3.11 or later from:
    echo    https://www.python.org/downloads/
    echo.
    echo  During installation, tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: ── Install dependencies on first run ────────────────────────────────────────
python -c "import rich" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  First run detected — installing dependencies...
    echo.
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo  [ERROR] Could not install packages automatically.
        echo  Run manually:  pip install rich numpy
        echo.
        pause
        exit /b 1
    )
    echo.
    echo  Dependencies installed. Starting game...
    echo.
)

:: ── Launch game ───────────────────────────────────────────────────────────────
python main.py

if %errorlevel% neq 0 (
    echo.
    echo  The game exited with an error. See the output above for details.
    pause
)
