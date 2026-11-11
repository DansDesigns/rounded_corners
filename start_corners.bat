@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Rounded Corners

rem Keep errors visible. The settings window runs in this same Python
rem process; only the background corner overlay uses pythonw.exe.
if not exist "%~dp0rounded_corners.py" (
    echo ERROR: rounded_corners.py was not found next to start_corners.bat.
    goto :failed
)

set "PYTHON=%~dp0venv\Scripts\python.exe"
set "PYTHONW=%~dp0venv\Scripts\pythonw.exe"

if not exist "%PYTHON%" (
    echo Creating Rounded Corners Python environment...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv "%~dp0venv"
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo ERROR: Python 3 was not found. Install Python 3 with tkinter support.
            goto :failed
        )
        python -m venv "%~dp0venv"
    )
    if errorlevel 1 goto :failed
)

if not exist "%PYTHON%" (
    echo ERROR: Unable to create the Python virtual environment.
    goto :failed
)

"%PYTHON%" -c "import tkinter, PIL, screeninfo" >nul 2>&1
if errorlevel 1 (
    echo Checking and installing Rounded Corners dependencies...
    "%PYTHON%" -m pip install pillow screeninfo
    if errorlevel 1 goto :failed
    "%PYTHON%" -c "import tkinter, PIL, screeninfo"
    if errorlevel 1 (
        echo ERROR: Python tkinter is missing. Install a Python distribution with Tcl/Tk support.
        goto :failed
    )
)

rem Shortcut creation is optional for opening settings. Report errors but
rem do not prevent the configuration window from appearing.
echo Updating Windows shortcuts...
"%PYTHON%" "%~dp0rounded_corners.py" --install-shortcuts
if errorlevel 1 (
    echo WARNING: Shortcuts could not be updated. The settings window will still open.
)

rem The overlay has its own enabled setting and single-instance lock.
rem Run only the overlay hidden; leave the GUI foreground to expose errors.
if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "%~dp0rounded_corners.py" --overlay
) else (
    start "" /B "%PYTHON%" "%~dp0rounded_corners.py" --overlay
)

echo Opening Rounded Corners settings...
"%PYTHON%" "%~dp0rounded_corners.py" --settings
if errorlevel 1 goto :failed

endlocal
exit /b 0

:failed
echo.
echo Rounded Corners could not start. See the error above.
pause
endlocal
exit /b 1
