"""
Роутер для управления риск-политикой
"""
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

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


@router.post("/policy")
def risk_policy_set(policy: Dict[str, Any], _=Depends(require_api_key)):
    """
    Обновить риск-политику (deep merge с валидацией)
    
    Принимает полную или частичную политику напрямую (без обёртки "updates").
    Примеры см. в GET /risk/policy или docs/BEGINNER_GUIDE.md
    """
    base = load_policy() or {}
    try:
        # если база чистая — используем её
        base = RiskPolicy.model_validate(base).model_dump(exclude_none=True)
    except ValidationError:
        # если в базе мусор/старые поля — начинаем с пустой
        base = {}

    cur = _deep_merge_policy(base, policy or {})

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

