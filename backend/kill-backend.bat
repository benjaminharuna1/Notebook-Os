@echo off
setlocal

set "ENVFILE=%~dp0.env"
set "PORT=8199"

if exist "%ENVFILE%" (
    for /f "tokens=1,* delims==" %%a in ('findstr /i "PORT" "%ENVFILE%"') do (
        set "PORT=%%b"
    )
)

echo Killing process on port %PORT%...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr :%PORT% ^| findstr LISTENING') do (
    echo   PID %%p
    taskkill /F /PID %%p >nul 2>&1
)
echo Done.
