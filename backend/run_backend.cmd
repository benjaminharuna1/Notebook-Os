@echo off
cd /d "%~dp0"
if not exist "..\logs" mkdir "..\logs"

rem Run uvicorn through the venv's interpreter instead of the `uvicorn.exe`
rem console script. That .exe is a uv trampoline which can fail with
rem "failed to canonicalize script path" when it cannot resolve the path baked
rem into it; `-m uvicorn` has no such dependency.
if not exist ".venv\Scripts\python.exe" (
  echo [NARA] No virtualenv found at .venv\Scripts\python.exe
  echo [NARA] Create it first:
  echo          uv venv
  echo          uv pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

echo [NARA] Backend starting...
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '..\logs\backend.log'"
echo.
echo [NARA] Backend stopped. Errors (if any) are shown above and saved in logs\backend.log.
pause
