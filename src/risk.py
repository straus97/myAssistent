from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Tuple, List
import json
import math
import pandas as pd

CFG_DIR = Path("artifacts") / "config"
CFG_DIR.mkdir(parents=True, exist_ok=True)
POLICY_PATH = CFG_DIR / "policy.json"

DEFAULT_POLICY: Dict[str, Any] = {
    # --- общие фильтры/порог для сигналов ---
    "min_prob_gap": 0.02,
    "cooldown_minutes": 90,
    "block_if_dead_volatility": True,
    "volatility_thresholds": {
        "15m": {"dead": 0.0040, "hot": 0.0150},
        "1h": {"dead": 0.0060, "hot": 0.0200},
        "4h": {"dead": 0.0080, "hot": 0.0250},
        "1d": {"dead": 0.0120, "hot": 0.0350},
    },
    # --- уведомления ---
    "notify": {"on_buy": True, "radar": False, "radar_gap": 0.01},
    # --- авто-действия ---
    "auto": {
        "trade_on_buy": False,
        "close_on_strong_flat": False,
        # доля капитала под покупку в зависимости от волатильности рынка
        "buy_fraction": {"dead": 0.05, "normal": 0.10, "hot": 0.07},
        "max_positions_per_symbol": 1,
    },
    # --- монитор портфеля ---
    "monitor": {
        "enabled": True,
        "flat_after": -0.01,  # если позиция ушла ниже -1% — предложить закрыть
        "partial_at": 0.03,  # если прибыль > +3% — частично зафиксировать
        "partial_size": 0.30,  # размер частичного закрытия
        "timeframe": "15m",
    },
    # --- news radar ---
    "news_radar": {
        "enabled": True,
        "window_minutes": 60,
        "lookback_windows": 6,
        "min_new": 6,
        "min_ratio_vs_prev": 2.0,
        "min_unique_sources": 3,
        "min_sentiment_abs": 0.0,
        "symbols": {
            "BTC/USDT": ["btc", "bitcoin"],
            "ETH/USDT": ["eth", "ethereum"],
        },
        "cooldown_minutes": 60,
    },
    # --- правила evaluate_filters ---
    "filters": {
        "min_rel_volume": 0.20,  # объём текущего бара >= 20% среднего(50)
        "max_bar_change": 0.03,  # отсечка «перегретого» бара: |close/prev_close-1| <= 3%
        "ema_fast": 20,
        "ema_slow": 50,
        "require_uptrend": False,  # если True — требуем EMA_fast >= EMA_slow
    },
}


def load_policy() -> Dict[str, Any]:
    if POLICY_PATH.exists():
        try:
            cfg = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_POLICY, **(cfg or {})}
        except Exception:
            pass
    POLICY_PATH.write_text(json.dumps(DEFAULT_POLICY, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEFAULT_POLICY.copy()


def save_policy(cfg: Dict[str, Any]) -> None:
    data = {**DEFAULT_POLICY, **(cfg or {})}
    POLICY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def evaluate_filters(
    row: pd.Series, df: pd.DataFrame, policy: Dict[str, Any], timeframe: str, last_bar_ts
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Возвращает (allow, reasons[], metrics{}).
    Лёгкие фильтры: объём, перегретый бар, тренд по EMA.
    """
    reasons: List[str] = []
    metrics: Dict[str, Any] = {}

    fs = policy.get("filters") or {}
    min_rel_vol = float(fs.get("min_rel_volume", 0.2))
    max_bar_ch = float(fs.get("max_bar_change", 0.03))
    ema_fast = int(fs.get("ema_fast", 20))
    ema_slow = int(fs.get("ema_slow", 50))
    require_uptrend = bool(fs.get("require_uptrend", False))

    # --- объём относительно среднего(50)
    vol = float(row.get("volume", float("nan")) or float("nan"))
    vol_mean = float(df["volume"].rolling(50, min_periods=10).mean().iloc[-1]) if "volume" in df else float("nan")
    rel_vol = (vol / vol_mean) if (vol_mean and vol_mean > 0) else float("nan")
    metrics.update({"volume": vol, "volume_mean50": vol_mean, "volume_rel": rel_vol})
    if not math.isnan(rel_vol) and rel_vol < min_rel_vol:
        reasons.append(f"low_volume_rel {rel_vol:.2f} < {min_rel_vol:.2f}")

    # --- величина бара
    if "open" in row:
        prev = float(row["open"])
        bar_ch = (float(row["close"]) / prev - 1.0) if prev > 0 else 0.0
    else:
        prevc = float(df["close"].shift(1).iloc[-1])
        bar_ch = (float(row["close"]) / prevc - 1.0) if prevc > 0 else 0.0
    metrics["bar_change"] = bar_ch
    if abs(bar_ch) > max_bar_ch:
        reasons.append(f"bar_too_large {bar_ch:+.2%} > {max_bar_ch:.2%}")

    # --- тренд по EMA
    ema_f = _ema(df["close"], ema_fast).iloc[-1]
    ema_s = _ema(df["close"], ema_slow).iloc[-1]
    trend_up = bool(ema_f >= ema_s)
    metrics.update({"ema_fast": float(ema_f), "ema_slow": float(ema_s), "trend_up": trend_up})
    if require_uptrend and not trend_up:
        reasons.append("no_uptrend")

    allow = len(reasons) == 0
    return allow, reasons, metrics
