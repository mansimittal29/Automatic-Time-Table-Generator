@echo off
setlocal
cd /d "%~dp0"

set "VENV_DIR=.venv"
if exist "..\.venv\Scripts\python.exe" (
    set "VENV_DIR=..\.venv"
)

echo ================================================
echo Automated Academic Timetable Scheduling Demo
echo ================================================

if exist "%VENV_DIR%\Scripts\python.exe" goto install_deps

echo [1/4] Creating virtual environment...
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    py -3 -m venv .venv
) else (
    python -m venv .venv
)
set "VENV_DIR=.venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

:install_deps
echo [2/4] Activating environment...
call "%VENV_DIR%\Scripts\activate.bat"
if %ERRORLEVEL% neq 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [3/4] Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo Dependency installation failed.
    pause
    exit /b 1
)

echo [4/5] Running database migration...
python migrate_db.py
if %ERRORLEVEL% neq 0 (
    echo Database migration failed.
    pause
    exit /b 1
)

echo [5/5] Starting server and opening browser...
start "" "http://127.0.0.1:5000"
python app.py

echo Server stopped.
pause
