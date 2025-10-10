"""
Роутер для управления риск-политикой
"""
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError, ConfigDict

from src.dependencies import require_api_key
from src.risk import load_policy, save_policy
from src.risk_schema import Policy as RiskPolicy
from src.utils import _deep_merge_policy


router = APIRouter(prefix="/risk", tags=["Risk"])


@router.get("/policy")
def risk_policy_get():
    """Получить текущую риск-политику"""
    p = load_policy() or {}
    try:
        p = RiskPolicy.model_validate(p).model_dump(exclude_none=True)
    except ValidationError:
        # если файл кривой — просто вернём как есть (чтобы можно было починить POST'ом)
        pass
    return p


class RiskPolicyUpdate(BaseModel):
    """Обновление риск-политики (deep merge)"""

    updates: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "updates": {
                    "monitor": {
                        "enabled": True,
                        "timeframe": "15m",
                        "partial_at": 0.03,
                        "partial_size": 0.30,
                        "flat_after": -0.01,
                        "cooldown_minutes": 60,
                        "min_ret_change": 0.005,
                        "types": ["partial", "flat"],
                        "only_symbols": ["ETH/USDT"],
                        "exclude_symbols": [],
                    }
                }
            }
        }
    )


@router.post("/policy")
def risk_policy_set(req: RiskPolicyUpdate, _=Depends(require_api_key)):
    """Обновить риск-политику (deep merge с валидацией)"""
    base = load_policy() or {}
    try:
        # если база чистая — используем её
        base = RiskPolicy.model_validate(base).model_dump(exclude_none=True)
    except ValidationError:
        # если в базе мусор/старые поля — начинаем с пустой
        base = {}

    cur = _deep_merge_policy(base, req.updates or {})

    try:
        valid = RiskPolicy.model_validate(cur).model_dump(exclude_none=True)
    except ValidationError as e:
        errs = []
        for er in e.errors():
            loc = ".".join(str(x) for x in er.get("loc", []))
            msg = er.get("msg", "invalid value")
            errs.append(f"{loc}: {msg}")
        raise HTTPException(status_code=422, detail={"status": "error", "errors": errs})
    save_policy(valid)
    return {"status": "ok", "policy": valid}

