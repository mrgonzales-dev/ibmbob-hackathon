@echo off
setlocal

set "DIR=%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo python not found on PATH. 1>&2
    exit /b 1
)

python "%DIR%bob_the_builder.py" %*
exit /b %errorlevel%
