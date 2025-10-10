from __future__ import annotations
from pathlib import Path
import json
from typing import Dict, Any

CFG_DIR = Path("artifacts") / "config"
CFG_DIR.mkdir(parents=True, exist_ok=True)
POLICY_PATH = CFG_DIR / "model_policy.json"

DEFAULT_POLICY: Dict[str, Any] = {
    # если последняя модель для пары старше N дней — переобучаем
    "max_age_days": 7,
    # если ROC-AUC ниже порога — переобучаем
    "retrain_if_auc_below": 0.55,
    # минимально допустимый размер датасета для тренировки
    "min_train_rows": 200,
    # промоутить новую модель, если AUC вырос минимум на:
    "promote_if_auc_gain": 0.005,
}


def load_model_policy() -> Dict[str, Any]:
    """Загружает политику переобучения; при ошибке/отсутствии — возвращает дефолт и сохраняет его."""
    if POLICY_PATH.exists():
        try:
            cfg = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_POLICY, **(cfg or {})}
        except Exception:
            pass
    # если файла нет или он битый — пишем дефолт
    POLICY_PATH.write_text(json.dumps(DEFAULT_POLICY, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEFAULT_POLICY.copy()


def save_model_policy(cfg: Dict[str, Any]) -> None:
    """Сохраняет политику (поверх дефолта, чтобы новые поля появлялись автоматически)."""
    data = {**DEFAULT_POLICY, **(cfg or {})}
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    POLICY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
