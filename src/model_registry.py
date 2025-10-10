from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict
import json
from sqlalchemy.orm import Session
from src.db import ModelRun
from src.modeling import load_latest_model  # возвращает (model, feature_cols, threshold, model_path)

CFG_DIR = Path("artifacts") / "config"
CFG_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_PATH = CFG_DIR / "active_models.json"


def _read_map() -> Dict[str, str]:
    if ACTIVE_PATH.exists():
        try:
            return json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _write_map(data: Dict[str, str]) -> None:
    ACTIVE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(ex: str, sym: str, tf: str, hz: int) -> str:
    return f"{ex.lower()}|{sym.upper()}|{tf}|{int(hz)}"


def set_active_model(ex: str, sym: str, tf: str, hz: int, model_path: str) -> None:
    mp = _read_map()
    mp[_key(ex, sym, tf, hz)] = model_path
    _write_map(mp)


def get_active_model_path(ex: str, sym: str, tf: str, hz: int) -> Optional[str]:
    return _read_map().get(_key(ex, sym, tf, hz))


def choose_latest_model_path(db: Session, ex: str, sym: str, tf: str, hz: int) -> Optional[str]:
    row = (
        db.query(ModelRun)
        .filter(
            ModelRun.exchange == ex,
            ModelRun.symbol == sym,
            ModelRun.timeframe == tf,
            ModelRun.horizon_steps == hz,
        )
        .order_by(ModelRun.id.desc())
        .first()
    )
    return row.model_path if row and row.model_path else None


def load_model_for(db: Session, ex: str, sym: str, tf: str, hz: int):
    """
    Приоритет:
      1) вручную выбранная активная модель (active_models.json)
      2) последний успешный ModelRun для этой пары/ТФ/горизонта
      3) общий fallback: load_latest_model() без фильтра (как раньше)
    """
    # 1) ручной выбор
    path = get_active_model_path(ex, sym, tf, hz)
    if path:
        try:
            return load_latest_model(model_path=path)
        except FileNotFoundError:
            pass

    # 2) последний прогон по фильтру
    path2 = choose_latest_model_path(db, ex, sym, tf, hz)
    if path2:
        try:
            return load_latest_model(model_path=path2)
        except FileNotFoundError:
            pass

    # 3) общий fallback
    return load_latest_model()
