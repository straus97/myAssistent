"""
Роутер для создания бэкапов (snapshot)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends

from src.dependencies import require_api_key, ok


router = APIRouter(prefix="/backup", tags=["Backup"])


@router.post("/snapshot")
def backup_snapshot(_=Depends(require_api_key)):
    """Создать snapshot бэкап (БД + артефакты)"""
    # TODO: перенести реализацию из main.py (создание ZIP-архива)
    return ok(message="Backup snapshot created (stub)")


# NOTE: Этот роутер содержит заглушку для backup эндпоинта.
# Для полной реализации нужно перенести код создания ZIP-архива из main.py

