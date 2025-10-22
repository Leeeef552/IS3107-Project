@echo off
REM ============================================================================
REM Bitcoin Analytics Dashboard Launcher (Windows)
REM ============================================================================

setlocal

REM Navigate to project root (parent of bin/)
cd /d "%~dp0\.."

set PORT=%1
if "%PORT%"=="" set PORT=8501

echo ==========================================
echo  Bitcoin Analytics Dashboard
echo ==========================================
echo.

REM Check for virtual environment
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment (venv)...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment (.venv)...
    call .venv\Scripts\activate.bat
) else (
    echo Warning: No virtual environment found
    echo Consider creating one: python -m venv venv
    pause
)

echo.
echo Running pre-flight checks...

REM Check Docker (basic check)
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running
    echo Please start Docker Desktop and try again
    pause
    exit /b 1
)
echo [OK] Docker is running

REM Check TimescaleDB
docker ps | findstr timescaledb >nul
if %errorlevel% neq 0 (
    echo ERROR: TimescaleDB container is not running
    echo.
    echo To start TimescaleDB:
    echo   docker start timescaledb
    echo.
    pause
    exit /b 1
)
echo [OK] TimescaleDB is running

echo.
echo ==========================================
echo  Starting Dashboard
echo ==========================================
echo.
echo Dashboard will open at: http://localhost:%PORT%
echo.
echo Features:
echo   - Real-time Bitcoin price
echo   - Interactive price charts
echo   - News sentiment analysis
echo   - Fear ^& Greed Index
echo   - Currency selector (USD/SGD)
echo.
echo Tips:
echo   - Press Ctrl+C to stop the dashboard
echo   - Start updater for real-time data: start_updater.bat
echo.
echo ==========================================
echo.

REM Launch Streamlit
streamlit run dashboard/app.py ^
  --server.port=%PORT% ^
  --server.headless=true ^
  --browser.gatherUsageStats=false

pause
