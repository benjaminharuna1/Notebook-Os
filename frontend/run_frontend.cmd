@echo off
cd /d "%~dp0"
if not exist "..\logs" mkdir "..\logs"
echo [NARA] Frontend starting...
npm run dev 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '..\logs\frontend.log'"
echo.
echo [NARA] Frontend stopped. Errors (if any) are shown above and saved in logs\frontend.log.
pause
