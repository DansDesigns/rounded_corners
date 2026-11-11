@echo off
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    python -m venv "venv"
    if errorlevel 1 exit /b 1
)

set "PYTHON=%~dp0venv\Scripts\python.exe"
set "PYTHONW=%~dp0venv\Scripts\pythonw.exe"

"%PYTHON%" -c "import PIL, screeninfo" >nul 2>&1
if errorlevel 1 (
    "%PYTHON%" -m pip install pillow screeninfo --quiet
    if errorlevel 1 exit /b 1
)

rem Install/refresh Windows Start Menu settings shortcut, and the separate
rem Startup overlay shortcut (only if enabled in saved settings).
"%PYTHON%" "%~dp0rounded_corners.py" --install-shortcuts
if errorlevel 1 exit /b 1

rem Start the overlay if configured to run; the app blocks duplicate overlays.
start "" "%PYTHONW%" "%~dp0rounded_corners.py" --overlay

rem When launched manually, show settings instead of opening a second overlay.
start "" "%PYTHONW%" "%~dp0rounded_corners.py" --settings
endlocal
