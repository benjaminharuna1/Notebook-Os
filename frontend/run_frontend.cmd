@echo off
cd /d "%~dp0"
if not exist "..\logs" mkdir "..\logs"
echo [Notebook OS] Frontend starting...
npm run dev 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '..\logs\frontend.log'"
echo.
echo [Notebook OS] Frontend stopped. Errors (if any) are shown above and saved in logs\frontend.log.
pause
