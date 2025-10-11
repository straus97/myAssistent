@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >NUL
title MyAssistant Full Stack Launcher

pushd C:\AI\myAssistent

echo ====================================
echo   MyAssistant Full Stack Launcher
echo ====================================
echo.
echo Этот скрипт запустит:
echo 1. Docker (PostgreSQL, MLflow, Prometheus, Grafana)
echo 2. Backend API (FastAPI на :8000)
echo 3. Streamlit UI (:8501)
echo 4. Frontend (Next.js на :3000)
echo.
echo Требования:
echo - Docker Desktop должен быть запущен
echo - Node.js 18+ установлен
echo - Python 3.11+ установлен
echo.
pause

REM === Проверка Docker ===
echo [*] Проверка Docker...
docker --version >NUL 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker не найден! Установите Docker Desktop.
    echo     Скачать: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)

docker ps >NUL 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker daemon не запущен!
    echo     Запустите Docker Desktop и повторите попытку.
    pause
    exit /b 1
)

echo [OK] Docker работает

REM === Проверка Node.js ===
echo [*] Проверка Node.js...
node --version >NUL 2>&1
if %errorlevel% neq 0 (
    echo [!] Node.js не найден! Установите Node.js 18+
    echo     Скачать: https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Node.js установлен

REM === Создание директорий ===
if not exist logs md logs
if not exist artifacts md artifacts

REM === Python venv ===
if not exist .venv\Scripts\python.exe (
  echo [*] Создаю виртуальное окружение...
  py -m venv .venv || (echo [!] Не удалось создать venv & pause & exit /b 1)
)

set "PY=.\.venv\Scripts\python.exe"
set LOG_LEVEL=DEBUG
%PY% --version || (echo [!] Не найден интерпретатор %PY% & pause & exit /b 1)

if not exist .venv\_deps.ok (
  echo [*] Устанавливаю Python зависимости...
  %PY% -m pip install --upgrade pip && ^
  %PY% -m pip install -r requirements.txt || (echo [!] Ошибка установки зависимостей & pause & exit /b 1)
  echo ok > .venv\_deps.ok
)

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM === MyAssistant config ===
REM Читаем настройки из .env файла (если существует)
if exist .env (
    echo [*] Загружаю настройки из .env
    for /f "usebackq tokens=1,* delims==" %%a in (.env) do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            set "%%a=%%b"
        )
    )
) else (
    echo [!] Файл .env не найден. Запусти: python setup_env.py
    pause
    exit /b 1
)

REM Fallback значения если что-то не указано
if not defined API_KEY set API_KEY=dev_api_key_for_testing_only
if not defined DATABASE_URL set DATABASE_URL=sqlite:///./assistant.db
if not defined TRADE_MODE set TRADE_MODE=live
if not defined ENABLE_METRICS set ENABLE_METRICS=true
if not defined MLFLOW_TRACKING_URI set MLFLOW_TRACKING_URI=http://localhost:5000

REM === Запуск Docker Compose ===
echo [*] Запускаю Docker контейнеры (PostgreSQL, MLflow, Prometheus, Grafana)...
echo [*] Примечание: pgbouncer пропускается (опциональный, для production)
docker-compose up -d postgres mlflow prometheus grafana

echo [*] Ожидание готовности сервисов (15 сек)...
timeout /t 15 /nobreak >NUL

REM === Запуск Backend ===
echo [*] Запускаю Backend API → http://127.0.0.1:8000
echo [*] MLFLOW_TRACKING_URI = %MLFLOW_TRACKING_URI%
start "backend" /D "%CD%" cmd /k "set MLFLOW_TRACKING_URI=%MLFLOW_TRACKING_URI% && set ENABLE_METRICS=%ENABLE_METRICS% && set API_KEY=%API_KEY% && set DATABASE_URL=%DATABASE_URL% && .\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --log-level debug"

timeout /t 3 /nobreak >NUL

REM === Запуск Streamlit UI ===
echo [*] Запускаю Streamlit UI → http://localhost:8501
start "streamlit-ui" cmd /k "%PY% -m streamlit run streamlit_app.py --server.headless true --server.port 8501"

timeout /t 2 /nobreak >NUL

REM === Запуск Frontend (Next.js) ===
echo [*] Проверка Frontend зависимостей...
cd frontend

if not exist .env.local (
    echo [*] Создаю frontend/.env.local из .env.example...
    copy .env.example .env.local >NUL
)

if not exist node_modules (
    echo [*] Устанавливаю npm зависимости...
    call npm install
)

echo [*] Запускаю Next.js Frontend → http://localhost:3000
start "nextjs-frontend" cmd /k "npm run dev"

cd ..

timeout /t 3 /nobreak >NUL

echo.
echo ====================================
echo   Все сервисы запущены!
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
echo Откроются автоматически через 3 секунды...

timeout /t 3 /nobreak >NUL

start "" http://127.0.0.1:8000/docs
start "" http://localhost:3000
start "" http://localhost:5000
start "" http://localhost:3001

echo.
echo [OK] Все окна ("backend", "streamlit-ui", "nextjs-frontend") должны остаться открытыми.
echo      Закроете окно — соответствующий сервис остановится.
echo.
echo Чтобы остановить Docker контейнеры:
echo   docker-compose down
echo.
pause
popd

