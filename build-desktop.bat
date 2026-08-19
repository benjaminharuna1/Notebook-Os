@echo off
echo ========================================
echo  Notebook AI OS - Desktop Build Script
echo ========================================
echo.

:: Step 1: Build Frontend
echo [1/3] Building frontend...
cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo ERROR: Frontend build failed!
    pause
    exit /b 1
)
cd ..
echo.

:: Step 2: Build Backend (PyInstaller)
echo [2/3] Building backend...
cd backend
call ..\backend\.venv\Scripts\pyinstaller.exe backend.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo ERROR: Backend build failed!
    pause
    exit /b 1
)
cd ..
echo.

:: Step 3: Build Electron Installer
echo [3/3] Building Electron installer...
cd desktop
call npm run build:electron
if %errorlevel% neq 0 (
    echo ERROR: Electron build failed!
    pause
    exit /b 1
)
cd ..
echo.

echo ========================================
echo  Build Complete!
echo ========================================
echo.
echo  Installer location:
echo  desktop\release\Notebook AI OS Setup 0.1.0.exe
echo.

:: Open the release folder
explorer "desktop\release"

pause
