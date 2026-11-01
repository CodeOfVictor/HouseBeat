@echo off
rem Runs HouseBeat from source. The first run creates a virtual environment and installs the dependencies.
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
    echo Setting up HouseBeat for the first time...
    python -m venv .venv || goto :nopython
    .venv\Scripts\python.exe -m pip install --upgrade pip >nul
    .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :eof
)
start "" .venv\Scripts\pythonw.exe housebeat.py
goto :eof

:nopython
echo Python 3.10 or newer is required: https://www.python.org/downloads/
pause
