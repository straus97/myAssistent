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
set API_KEY=803a29e730b47a595e38836abf8c19d7ef325b5790993e17d25515a47a3fc8b6
REM Unified database: используем assistant.db для всех данных
set DATABASE_URL=sqlite:///./assistant.db
set TRADE_MODE=live
set OFFLINE_DOCS=1
set ENABLE_DOCS=1
REM опционально, чтобы /artifacts открывались без заголовка (только локально!):
REM set PUBLIC_ARTIFACTS=1

echo [*] Запускаю backend → http://127.0.0.1:8000
start "backend" /D "%CD%" ".\.venv\Scripts\python.exe" -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --log-level debug >> logs\server.log 2>&1

timeout /t 3 /nobreak >NUL

echo [*] Запускаю UI → http://localhost:8501
start "ui" cmd /k "%PY% -m streamlit run streamlit_app.py --server.headless true --server.port 8501"

start "" http://127.0.0.1:8000/ping
start "" http://127.0.0.1:8000/docs
start "" http://localhost:8501

echo [OK] Два окна ("backend" и "ui") должны остаться открытыми. Закроешь окно — сервис остановится.
pause
popd
