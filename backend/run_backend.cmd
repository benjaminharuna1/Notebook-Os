@echo off
cd /d "%~dp0"
if not exist "..\logs" mkdir "..\logs"
echo [Notebook OS] Backend starting...
uv run uvicorn app.main:app --reload 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '..\logs\backend.log'"
echo.
echo [Notebook OS] Backend stopped. Errors (if any) are shown above and saved in logs\backend.log.
pause
