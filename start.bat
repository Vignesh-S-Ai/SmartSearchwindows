@echo off
REM Start script for Smart Search - Windows
REM Starts both the API backend and Electron frontend

echo ========================================
echo Starting Smart Search
echo ========================================

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Running setup...
    call setup.bat
)

REM Activate virtual environment
call venv\Scripts\activate

echo.
echo Starting API server...
start "Smart Search API" python -m api.main

REM Wait for API to start
timeout /t 3 /nobreak >nul

echo Starting Electron UI...
cd ui
call npm start
cd ..

echo.
echo Smart Search is running!
echo Press Ctrl+C in the API window to stop.
echo ========================================

pause
