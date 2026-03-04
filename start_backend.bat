@echo off
echo ============================================
echo   AgroVisus - Starting Backend Server
echo ============================================
echo.

cd /d "%~dp0"

echo Checking Python environment...
if not exist "agrovisus_simulation_engine\venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Expected: agrovisus_simulation_engine\venv\Scripts\python.exe
    pause
    exit /b 1
)

echo Installing/checking backend dependencies...
agrovisus_simulation_engine\venv\Scripts\pip.exe install uvicorn fastapi pydantic --quiet 2>nul

echo.
echo Starting FastAPI backend on http://localhost:8001 ...
echo Press Ctrl+C to stop.
echo.
agrovisus_simulation_engine\venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8001
pause
