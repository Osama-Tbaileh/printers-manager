@echo off
REM ============================================================================
REM USB Auto-Setup Script for Printer Server (Windows)
REM 
REM This script will:
REM 1. Clone the printer-manager repo from GitHub
REM 2. Create a Python virtual environment
REM 3. Install all requirements
REM 4. Run the server
REM
REM Usage: Double-click this file after plugging in the USB!
REM ============================================================================

color 0B
echo.
echo ========================================
echo   Printer Server - USB Auto Setup
echo ========================================
echo.

REM Configuration
set GITHUB_REPO=YOUR_GITHUB_USERNAME/printers-manager
set INSTALL_DIR=%USERPROFILE%\printer-server
set REPO_URL=https://github.com/%GITHUB_REPO%.git

REM Check if git is installed
echo [1/6] Checking dependencies...
where git >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: Git is not installed!
    echo Please install Git from: https://git-scm.com/download/win
    pause
    exit /b 1
)

where python >nul 2>nul
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: Python is not installed!
    echo Please install Python from: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Dependencies found
echo.

REM Ask for installation directory
echo [2/6] Setting up installation directory...
echo Default: %INSTALL_DIR%
set /p "custom_dir=Enter custom path or press Enter to use default: "
if not "%custom_dir%"=="" set INSTALL_DIR=%custom_dir%

if exist "%INSTALL_DIR%" (
    echo Directory already exists!
    set /p "remove=Remove and reinstall? (y/n): "
    if /i "%remove%"=="y" (
        rmdir /s /q "%INSTALL_DIR%"
        echo [OK] Old installation removed
    ) else (
        echo Installation cancelled.
        pause
        exit /b 1
    )
)
echo.

REM Clone repository
echo [3/6] Cloning repository from GitHub...
echo Repository: %REPO_URL%
git clone %REPO_URL% "%INSTALL_DIR%"
if %errorlevel% neq 0 (
    color 0C
    echo ERROR: Failed to clone repository!
    echo Please check your internet connection and repository URL.
    pause
    exit /b 1
)
echo [OK] Repository cloned
echo.

REM Create virtual environment
echo [4/6] Creating Python virtual environment...
cd /d "%INSTALL_DIR%"
python -m venv venv
echo [OK] Virtual environment created
echo.

REM Install requirements
echo [5/6] Installing Python packages...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
if exist requirements.txt (
    pip install -r requirements.txt
    echo [OK] All packages installed
) else (
    color 0E
    echo WARNING: requirements.txt not found!
)
echo.

REM Configuration
echo [6/6] Configuring server...
set /p "printer_ips=Enter printer IP addresses (comma-separated) or press Enter to skip: "

if not "%printer_ips%"=="" (
    echo # Printer Configuration > printer_config.txt
    echo %printer_ips% >> printer_config.txt
    echo [OK] Printer configuration saved
)

REM Create start script
echo @echo off > start_server.bat
echo cd /d "%%~dp0" >> start_server.bat
echo call venv\Scripts\activate.bat >> start_server.bat
echo python server.py >> start_server.bat
echo pause >> start_server.bat

echo.
color 0A
echo ========================================
echo     Installation Complete!
echo ========================================
echo.
echo Installation Directory: %INSTALL_DIR%
echo.
echo To start the server:
echo   1. Go to: %INSTALL_DIR%
echo   2. Double-click: start_server.bat
echo.
echo To test the server:
echo   curl http://localhost:3006/health
echo.
set /p "start_now=Start server now? (y/n): "
if /i "%start_now%"=="y" (
    echo.
    echo Starting server...
    call start_server.bat
) else (
    echo.
    echo Setup complete! Run start_server.bat when ready.
)

pause

