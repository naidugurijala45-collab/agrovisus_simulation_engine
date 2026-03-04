@echo off
echo ============================================
echo   AgroVisus - Starting Frontend Dev Server
echo ============================================
echo.

cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo Installing dependencies...
    npm install
)

echo.
echo Starting Vite dev server on http://localhost:5173 ...
echo Press Ctrl+C to stop.
echo.
npm run dev
pause
