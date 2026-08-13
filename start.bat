@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"

title Notebook OS - Startup
echo ============================================
echo   Notebook OS - Startup
echo   Backend  : http://127.0.0.1:8000
echo   Frontend : http://127.0.0.1:5173
echo   Logs     : %ROOT%logs
echo ============================================
echo.

echo [1/2] Starting backend...
start "Notebook OS - Backend" cmd /k ""%ROOT%backend\run_backend.cmd""

echo [2/2] Starting frontend...
start "Notebook OS - Frontend" cmd /k ""%ROOT%frontend\run_frontend.cmd""

echo.
echo   Both services are starting in separate windows.
echo   You can close this window now.
ping -n 4 127.0.0.1 >nul
