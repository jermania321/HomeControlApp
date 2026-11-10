@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo ERROR: The app environment is not set up yet.
    echo Double-click setup.bat first, then run start.bat again.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" -m homecontrol

endlocal
