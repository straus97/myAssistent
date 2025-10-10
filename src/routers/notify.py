"""
Роутер для настроек уведомлений (Telegram)
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.dependencies import require_api_key
from src.notify import get_notify_config, save_notify_config, send_telegram


router = APIRouter(prefix="/notify", tags=["Notify"])


@router.get("/config")
def notify_get():
    """Получить конфигурацию уведомлений (с маскировкой токенов)"""
    return get_notify_config(mask=True)


class NotifyUpdate(BaseModel):
    """Обновление конфигурации уведомлений"""

    enabled: Optional[bool] = None
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[int] = None
    rules: Optional[Dict[str, Any]] = None


@router.post("/config")
def notify_set(req: NotifyUpdate, _=Depends(require_api_key)):
    """Обновить конфигурацию уведомлений"""
    cfg = get_notify_config(mask=False)
    if req.enabled is not None:
        cfg["enabled"] = bool(req.enabled)
    if req.telegram_token is not None:
        cfg.setdefault("telegram", {})["token"] = req.telegram_token.strip()
    if req.telegram_chat_id is not None:
        cfg.setdefault("telegram", {})["chat_id"] = int(req.telegram_chat_id)
    if req.rules is not None:
        cfg["rules"] = {**(cfg.get("rules") or {}), **req.rules}
    save_notify_config(cfg)
    return {"status": "ok", "config": get_notify_config(mask=True)}


@router.post("/test")
def notify_test(_=Depends(require_api_key)):
    """Отправить тестовое сообщение в Telegram"""
    ok, detail = send_telegram("✅ Тестовое сообщение от My Assistant")
    return {"status": "ok" if ok else "error", "detail": detail}

