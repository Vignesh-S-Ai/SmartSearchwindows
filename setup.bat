@echo off
REM Setup script for Smart Search - Windows
REM Run this once to install dependencies

echo ========================================
echo Smart Search Setup
echo ========================================

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

echo Python found. Installing dependencies...

REM Create virtual environment (optional but recommended)
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
call venv\Scripts\activate

REM Upgrade pip
python -m pip install --upgrade pip

REM Install requirements
echo Installing Python packages...
pip install -r requirements.txt

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo 1. Copy .env.example to .env and add your GEMINI_API_KEY
echo 2. Run start.bat to start the application
echo.
pause
