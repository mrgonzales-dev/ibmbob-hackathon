@echo off
setlocal
set "DIR=%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo python not found on PATH. 1>&2
    exit /b 1
)

python "%DIR%..\skills\bob-upgrade\src\run.py" %*
exit /b %errorlevel%
