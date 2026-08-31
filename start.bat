@echo off
echo Starting Inventory Management System...

cd /d "%~dp0backend"
echo Starting Backend API (FastAPI) on port 8000...
start "Backend API" cmd /c "call ..\venv\Scripts\activate.bat && uvicorn main:app --host 0.0.0.0 --port 8000"

cd /d "%~dp0frontend"
echo Starting Frontend UI (React) on port 5173...
start "Frontend UI" cmd /c "npm run dev -- --host 0.0.0.0"

echo.
echo Servers are starting in new command prompt windows.
echo - Frontend UI will be available at: http://localhost:5173
echo - Backend API will be available at: http://localhost:8000
echo.
pause
