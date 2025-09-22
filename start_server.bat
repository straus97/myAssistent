@echo off
REM === Путь к проекту ===
cd /d C:\AI\myAssistent

REM === Гарантируем наличие папки logs ===
if not exist logs mkdir logs

REM === Небольшая пауза, чтобы сеть/диски успели подняться ===
timeout /t 5 /nobreak >NUL

REM === Запуск uvicorn через интерпретатор venv ===
REM 1) УКАЖИ корректный путь к python.exe внутри твоего виртуального окружения:
REM    Пример для venv проекта: C:\AI\my-assistant\.venv\Scripts\python.exe
REM 2) Если сомневаешься — в PyCharm открой Terminal и выполни: where python

"C:\AI\myAssistent\.venv\Scripts\python.exe" -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --log-level info >> logs\server.log 2>&1
