"""
Роутер для формирования датасета (features + target)
"""
from __future__ import annotations
from pathlib import Path
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key, ok, err
from src.features import build_dataset


router = APIRouter(prefix="/dataset", tags=["Dataset"])


class DatasetBuildRequest(BaseModel):
    """Запрос на формирование датасета"""

    exchange: str = "bybit"
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
    horizon_steps: int = 6


@router.post("/build")
def dataset_build(req: DatasetBuildRequest, db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Формирование датасета с фичами и target для обучения модели"""
    try:
        df, feature_cols = build_dataset(db, req.exchange, req.symbol, req.timeframe, req.horizon_steps)
        if df.empty:
            err("dataset.empty", "пустой датасет", 409)
        info = {
            "rows": int(len(df)),
            "start": df.index[0].isoformat(),
            "end": df.index[-1].isoformat(),
            "n_features": len(feature_cols),
            "features": feature_cols[:10] + (["..."] if len(feature_cols) > 10 else []),
        }
        Path("artifacts").mkdir(exist_ok=True)
        csv_rel = Path("artifacts") / "dataset_preview.csv"
        df.head(200).to_csv(csv_rel, encoding="utf-8")
        info["preview_csv_url"] = f"/artifacts/{csv_rel.name}"
        return ok(info=info)
    except Exception as e:
        err("dataset.build_failed", str(e), 500)

