@echo off
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate
pip install pillow screeninfo

:: Add to startup folder automatically (only once)
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT=%STARTUP%\rounded_corners.lnk
set SCRIPT_DIR=%~dp0

if not exist "%SHORTCUT%" (
    echo Creating startup shortcut...
    powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%SCRIPT_DIR%start_corners.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.WindowStyle = 7; $s.Save()"
    echo Startup shortcut created - will now run on every login!
)

python rounded_corners.py %*
