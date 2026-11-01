@echo off
rem Builds dist\HouseBeat.exe (a single portable file) with PyInstaller.
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || goto :eof
python -m PyInstaller --noconfirm --clean housebeat.spec
