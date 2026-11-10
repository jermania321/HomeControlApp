@echo off
setlocal
cd /d "%~dp0"

echo Setting up HomeControlApp in a clean virtual environment...

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3.12 -m venv .venv
        if errorlevel 1 goto python39_fallback
    ) else (
        goto python_fallback
    )
)
goto install_dependencies

:python39_fallback
echo Python 3.12 was not available. Trying Python 3.9...
py -3.9 -m venv .venv
if errorlevel 1 goto python_fallback
goto install_dependencies

:python_fallback
echo Python launcher could not create a virtual environment. Trying "python"...
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found. Install Python 3.9 or newer and try again.
    pause
    exit /b 1
)
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Could not create the virtual environment.
    pause
    exit /b 1
)

:install_dependencies
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto install_failed

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_failed

".venv\Scripts\python.exe" -c "from PySide6.QtWidgets import QApplication; print('PySide6 import OK')"
if errorlevel 1 goto pyside_failed

echo.
echo Setup complete. Double-click start.bat to launch HomeControlApp.
pause
exit /b 0

:pyside_failed
echo.
echo ERROR: PySide6 could not load its native Windows libraries in this Python environment.
echo Try installing Python 3.12 from python.org, then rename .venv and run setup.bat again.
pause
exit /b 1

:install_failed
echo.
echo ERROR: Dependency installation failed. Check your internet connection and try setup.bat again.
pause
exit /b 1
