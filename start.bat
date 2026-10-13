@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0dist\SSHProxySwitch.exe" (
    start "" "%~dp0dist\SSHProxySwitch.exe"
    exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys, tkinter; assert sys.version_info >= (3, 9)" >nul 2>nul
    if not errorlevel 1 (
        py -3 "%~dp0tools\ssh_proxy_switch.py"
        if errorlevel 1 goto launch_failed
        exit /b 0
    )
)
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys, tkinter; assert sys.version_info >= (3, 9)" >nul 2>nul
    if not errorlevel 1 (
        python "%~dp0tools\ssh_proxy_switch.py"
        if errorlevel 1 goto launch_failed
        exit /b 0
    )
)
echo Python 3.9+ with Tkinter was not found.
echo Install Python, or use the packaged dist\SSHProxySwitch.exe.
pause
exit /b 1

:launch_failed
echo The application could not start. See the error above.
pause
exit /b 1
