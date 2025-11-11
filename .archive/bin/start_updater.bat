@echo off
REM ============================================================================
REM Bitcoin Price Data Continuous Updater Launcher (Windows)
REM ============================================================================

setlocal

REM Navigate to project root (parent of bin/)
cd /d "%~dp0\.."

set INTERVAL=%1
if "%INTERVAL%"=="" set INTERVAL=60

echo ========================================
echo Bitcoin Price Data Continuous Updater
echo ========================================
echo.
echo Update interval: %INTERVAL% seconds
echo.

REM Check for virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo Warning: No virtual environment found
    pause
)

echo.
echo Starting continuous updater...
echo Press Ctrl+C to stop
echo.

python -m scripts.continuous_updater --interval %INTERVAL%

pause

