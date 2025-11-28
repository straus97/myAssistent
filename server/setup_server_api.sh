#!/bin/bash
# Скрипт для создания API управления сервером
# Загрузите на сервер как setup_server_api.sh

echo "=== НАСТРОЙКА API УПРАВЛЕНИЯ СЕРВЕРОМ ==="

cd ~/myAssistent

# Создаем скрипт для API управления
cat > server_api.py << 'EOF'
#!/usr/bin/env python3
"""
API для управления сервером myAssistent
Добавляет эндпоинты для мониторинга и управления
"""

import subprocess
import json
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/server", tags=["Server Management"])

class ServerStatus(BaseModel):
    service_status: str
    uptime: str
    memory_usage: str
    disk_usage: str
    python_processes: int
    last_log_entries: list

@router.get("/status", response_model=ServerStatus)
async def get_server_status():
    """Получить статус сервера"""
    try:
        # Статус сервиса
        result = subprocess.run(['systemctl', 'is-active', 'myassistent'], 
                              capture_output=True, text=True)
        service_status = result.stdout.strip()
        
        # Время работы
        result = subprocess.run(['uptime'], capture_output=True, text=True)
        uptime = result.stdout.strip()
        
        # Использование памяти
        result = subprocess.run(['free', '-h'], capture_output=True, text=True)
        memory_usage = result.stdout.strip()
        
        # Использование диска
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        disk_usage = result.stdout.strip()
        
        # Процессы Python
        result = subprocess.run(['pgrep', '-f', 'python.*myAssistent'], 
                              capture_output=True, text=True)
        python_processes = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
        
        # Последние логи
        result = subprocess.run(['journalctl', '-u', 'myassistent', '-n', '5', '--no-pager'], 
                              capture_output=True, text=True)
        last_log_entries = result.stdout.strip().split('\n')
        
        return ServerStatus(
            service_status=service_status,
            uptime=uptime,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            python_processes=python_processes,
            last_log_entries=last_log_entries
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting server status: {str(e)}")

@router.post("/restart")
async def restart_service():
    """Перезапустить сервис myAssistent"""
    try:
        result = subprocess.run(['systemctl', 'restart', 'myassistent'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            return {"message": "Service restarted successfully"}
        else:
            raise HTTPException(status_code=500, detail=f"Failed to restart: {result.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restarting service: {str(e)}")

@router.post("/update")
async def update_code():
    """Обновить код с GitHub"""
    try:
        # Git pull
        result = subprocess.run(['git', 'pull', 'origin', 'main'], 
                              capture_output=True, text=True, cwd='/root/myAssistent')
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Git pull failed: {result.stderr}")
        
        # Restart service
        result = subprocess.run(['systemctl', 'restart', 'myassistent'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Service restart failed: {result.stderr}")
        
        return {"message": "Code updated and service restarted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating code: {str(e)}")

@router.get("/logs")
async def get_logs(lines: int = 50):
    """Получить последние логи"""
    try:
        result = subprocess.run(['journalctl', '-u', 'myassistent', '-n', str(lines), '--no-pager'], 
                              capture_output=True, text=True)
        return {"logs": result.stdout.strip().split('\n')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting logs: {str(e)}")
EOF

# Делаем скрипт исполняемым
chmod +x server_api.py

echo "API скрипт создан: server_api.py"
echo ""
echo "Для интеграции в основное приложение добавьте в src/main.py:"
echo "from server_api import router as server_router"
echo "app.include_router(server_router)"
echo ""
echo "Теперь доступны эндпоинты:"
echo "- GET /server/status - статус сервера"
echo "- POST /server/restart - перезапуск сервиса"
echo "- POST /server/update - обновление кода"
echo "- GET /server/logs - получение логов"
