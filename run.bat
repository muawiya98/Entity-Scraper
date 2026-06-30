@echo off
REM ---------------------------------------------------------------------------
REM Entity Scraper - one-click launcher for Windows
REM Creates a virtual environment, installs dependencies, and starts the app.
REM ---------------------------------------------------------------------------
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Installing dependencies (first run only may take a minute)...
".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

echo.
echo Starting Entity Scraper at http://127.0.0.1:5000
echo Press Ctrl+C to stop.
echo.
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py

pause
