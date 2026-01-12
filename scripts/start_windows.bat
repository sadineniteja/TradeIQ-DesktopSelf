@echo off
REM TradeIQ Desktop Launcher for Windows

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0
set APP_DIR=%SCRIPT_DIR%..

REM Change to app directory
cd /d "%APP_DIR%"

REM Check if Python 3 is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 3 is not installed. Please install Python 3.8 or higher.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo 📥 Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo ⚠️  .env file not found. Creating from template...
    if exist ".env.example" (
        copy .env.example .env
        echo ✅ Created .env file. Please edit it with your API keys.
    ) else (
        echo ⚠️  No .env.example found. You'll need to create .env manually.
    )
)

REM Set Flask environment
set FLASK_APP=app\python\app.py
set FLASK_ENV=development
set PYTHONPATH=%APP_DIR%\app\python;%PYTHONPATH%

REM Start Flask server
echo.
echo 🚀 Starting TradeIQ Desktop...
echo 📍 Server will be available at: http://127.0.0.1:5000
echo 📱 Open this URL in your browser
echo.
echo Press Ctrl+C to stop the server
echo.

python -m flask run --host=127.0.0.1 --port=5000

pause

