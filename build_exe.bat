@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys, tkinter; assert sys.version_info >= (3, 9)" >nul 2>nul
    if not errorlevel 1 (
        py -3 "%~dp0tools\build_exe.py"
        if errorlevel 1 goto build_failed
        goto build_success
    )
)
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys, tkinter; assert sys.version_info >= (3, 9)" >nul 2>nul
    if not errorlevel 1 (
        python "%~dp0tools\build_exe.py"
        if errorlevel 1 goto build_failed
        goto build_success
    )
)
echo Python 3.9+ with Tkinter was not found. Install Python first.
goto build_failed

:build_success
echo Build complete: %~dp0dist\SSHProxySwitch.exe
pause
exit /b 0

:build_failed
echo Build failed. See the error above.
pause
exit /b 1
