@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >NUL
title MyAssistant Full Stack Launcher

pushd C:\AI\myAssistent

echo ====================================
echo   MyAssistant Full Stack Launcher
echo ====================================
echo.
echo This script will start:
echo 1. Docker (PostgreSQL, MLflow, Prometheus, Grafana)
echo 2. Backend API (FastAPI on :8000)
echo 3. Streamlit UI (:8501)
echo 4. Frontend (Next.js on :3000)
echo.
echo Requirements:
echo - Docker Desktop must be running
echo - Node.js 18+ installed
echo - Python 3.11+ installed
echo.
pause

REM === Check Docker ===
echo [*] Checking Docker...
docker --version >NUL 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker not found! Install Docker Desktop.
    echo     Download: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

docker ps >NUL 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker daemon not running!
    echo     Start Docker Desktop and try again.
    pause
    exit /b 1
)

echo [OK] Docker is running

REM === Check Node.js ===
echo [*] Checking Node.js...
node --version >NUL 2>&1
if %errorlevel% neq 0 (
    echo [!] Node.js not found! Install Node.js 18+
    echo     Download: https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Node.js installed

REM === Create directories ===
if not exist logs md logs
if not exist artifacts md artifacts

REM === Python venv ===
if not exist .venv\Scripts\python.exe (
  echo [*] Creating virtual environment...
  py -m venv .venv
  if errorlevel 1 (
    echo [!] Failed to create venv
    pause
    exit /b 1
  )
)

set "PY=.\.venv\Scripts\python.exe"
set LOG_LEVEL=DEBUG
%PY% --version
if errorlevel 1 (
  echo [!] Python interpreter not found: %PY%
  pause
  exit /b 1
)

if not exist .venv\_deps.ok (
  echo [*] Installing Python dependencies...
  %PY% -m pip install --upgrade pip
  if errorlevel 1 (
    echo [!] Failed to upgrade pip
    pause
    exit /b 1
  )
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [!] Failed to install dependencies
    pause
    exit /b 1
  )
  echo ok > .venv\_deps.ok
)

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM === MyAssistant config ===
REM Read settings from .env file if exists
if exist .env (
    echo [*] Loading settings from .env
    for /f "usebackq tokens=1,* delims==" %%a in (.env) do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            set "%%a=%%b"
        )
    )
) else (
    echo [!] File .env not found. Run: python setup_env.py
    pause
    exit /b 1
)

REM Fallback values if not specified
if not defined API_KEY set API_KEY=dev_api_key_for_testing_only
if not defined DATABASE_URL set DATABASE_URL=sqlite:///./assistant.db
if not defined TRADE_MODE set TRADE_MODE=live
if not defined ENABLE_METRICS set ENABLE_METRICS=true
if not defined MLFLOW_TRACKING_URI set MLFLOW_TRACKING_URI=http://localhost:5000

REM === Start Docker Compose ===
echo [*] Starting Docker containers (PostgreSQL, MLflow, Prometheus, Grafana)...
echo [*] Note: pgbouncer skipped (optional, for production)
docker-compose up -d postgres mlflow prometheus grafana

echo [*] Waiting for services to be ready (15 sec)...
timeout /t 15 /nobreak >NUL

REM === Start Backend with Auto-Reload ===
echo [*] Starting Backend API at http://127.0.0.1:8000 (AUTO-RELOAD ENABLED)
echo [*] MLFLOW_TRACKING_URI = %MLFLOW_TRACKING_URI%
echo [*] Backend will auto-restart when Python files change
start "backend" /D "%CD%" cmd /k "set MLFLOW_TRACKING_URI=%MLFLOW_TRACKING_URI% && set ENABLE_METRICS=%ENABLE_METRICS% && set API_KEY=%API_KEY% && set DATABASE_URL=%DATABASE_URL% && .\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --log-level debug --reload"

timeout /t 3 /nobreak >NUL

REM === Start Streamlit UI with Auto-Reload ===
echo [*] Starting Streamlit UI at http://localhost:8501 (AUTO-RELOAD BUILT-IN)
echo [*] Streamlit will auto-reload when files change
start "streamlit-ui" cmd /k "%PY% -m streamlit run streamlit_app.py --server.headless true --server.port 8501"

timeout /t 2 /nobreak >NUL

REM === Start Frontend (Next.js) ===
echo [*] Checking Frontend dependencies...
cd frontend

if not exist .env.local (
    echo [*] Creating frontend/.env.local from .env.example...
    copy .env.example .env.local >NUL
)

if not exist node_modules (
    echo [*] Installing npm dependencies...
    call npm install
)

echo [*] Starting Next.js Frontend at http://localhost:3000 (HOT RELOAD BUILT-IN)
echo [*] Next.js will auto-reload when files change
start "nextjs-frontend" cmd /k "npm run dev"

cd ..

timeout /t 3 /nobreak >NUL

echo.
echo ====================================
echo   All services started!
echo ====================================
echo.
echo Backend API:    http://127.0.0.1:8000
echo Swagger UI:     http://127.0.0.1:8000/docs
echo Metrics:        http://127.0.0.1:8000/metrics
echo.
echo Streamlit UI:   http://localhost:8501
echo Next.js UI:     http://localhost:3000
echo.
echo MLflow UI:      http://localhost:5000
echo Prometheus:     http://localhost:9090
echo Grafana:        http://localhost:3001 (admin/admin)
echo.
echo Opening in browser in 3 seconds...

timeout /t 3 /nobreak >NUL

start "" http://127.0.0.1:8000/docs
start "" http://localhost:3000
start "" http://localhost:5000
start "" http://localhost:3001

echo.
echo [OK] All windows (backend, streamlit-ui, nextjs-frontend) should remain open.
echo      Closing a window will stop the corresponding service.
echo.
echo ====================================
echo   AUTO-RELOAD FEATURES ENABLED
echo ====================================
echo.
echo Backend (FastAPI):  Auto-restart on .py file changes (--reload)
echo Streamlit:          Auto-reload on .py file changes (built-in)
echo Next.js:            Hot reload on .tsx/.ts/.css changes (built-in)
echo.
echo NO NEED TO RESTART start_all.bat after code changes!
echo Just save your files and services will reload automatically.
echo.
echo To stop Docker containers:
echo   docker-compose down
echo.
pause
popd
