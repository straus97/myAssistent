@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >NUL
title MyAssistant launcher

pushd C:\AI\myAssistent

if not exist logs md logs
if not exist artifacts md artifacts

if not exist .venv\Scripts\python.exe (
  echo [*] Создаю виртуальное окружение...
  py -m venv .venv || (echo [!] Не удалось создать venv & pause & exit /b 1)
)

set "PY=.\.venv\Scripts\python.exe"
set LOG_LEVEL=DEBUG
%PY% --version || (echo [!] Не найден интерпретатор %PY% & pause & exit /b 1)

if not exist .venv\_deps.ok (
  echo [*] Устанавливаю зависимости...
  %PY% -m pip install --upgrade pip && ^
  %PY% -m pip install -r requirements.txt || (echo [!] Ошибка установки зависимостей & pause & exit /b 1)
  echo ok > .venv\_deps.ok
)

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM --- MyAssistant config ---
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

echo [*] Запускаю backend → http://127.0.0.1:8000
echo [*] MLFLOW_TRACKING_URI = %MLFLOW_TRACKING_URI%
start "backend" /D "%CD%" cmd /k "set MLFLOW_TRACKING_URI=%MLFLOW_TRACKING_URI% && set ENABLE_METRICS=%ENABLE_METRICS% && set API_KEY=%API_KEY% && set DATABASE_URL=%DATABASE_URL% && .\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --log-level debug"

timeout /t 3 /nobreak >NUL

echo [*] Запускаю UI → http://localhost:8501
start "ui" cmd /k "%PY% -m streamlit run streamlit_app.py --server.headless true --server.port 8501"

start "" http://127.0.0.1:8000/ping
start "" http://127.0.0.1:8000/docs
start "" http://localhost:8501

echo [OK] Два окна ("backend" и "ui") должны остаться открытыми. Закроешь окно — сервис остановится.
pause
popd
