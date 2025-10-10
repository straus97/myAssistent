"""
Общие утилиты для всего приложения
"""
from __future__ import annotations
from datetime import datetime, timezone as _tz
import pandas as pd


def _now_utc() -> datetime:
    """Текущее время в UTC"""
    try:
        return datetime.now(_tz.utc)
    except Exception:
        return datetime.utcnow().replace(tzinfo=_tz.utc)


def _radar_now_utc() -> datetime:
    """Текущее время для News Radar (алиас для единообразия)"""
    return _now_utc()


def _to_ms(dt: datetime) -> int:
    """Конвертирует datetime в миллисекунды Unix timestamp"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz.utc)
    return int(dt.timestamp() * 1000)


_TF_MIN = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def _tf_minutes(tf: str) -> int:
    """Конвертирует timeframe (1m, 5m, 1h, 4h, 1d) в минуты"""
    tf = (tf or "").lower()
    if tf in _TF_MIN:
        return _TF_MIN[tf]
    if tf.endswith("m"):
        try:
            return int(tf[:-1])
        except Exception:
            return 60
    if tf.endswith("h"):
        try:
            return int(tf[:-1]) * 60
        except Exception:
            return 60
    if tf.endswith("d"):
        try:
            return int(tf[:-1]) * 1440
        except Exception:
            return 1440
    return 60


def _deep_merge_policy(base: dict, updates: dict) -> dict:
    """
    Рекурсивно мёрджит словари: вложенные dict-ы объединяются, остальные значения перезаписываются.
    Списки НЕ склеиваются — второе значение полностью заменяет первое.
    """
    out = dict(base or {})
    for k, v in (updates or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge_policy(out[k], v)
        else:
            out[k] = v
    return out


def _policy_vol_thr(policy: dict, timeframe: str) -> dict:
    """Получает пороги волатильности (dead/hot) для timeframe из политики"""
    tf = (timeframe or "1h").lower()
    v = (policy or {}).get("volatility_thresholds") or {}
    defaults = {
        "15m": {"dead": 0.0025, "hot": 0.0090},
        "1h": {"dead": 0.0040, "hot": 0.0150},
        "4h": {"dead": 0.0060, "hot": 0.0200},
        "1d": {"dead": 0.0100, "hot": 0.0300},
    }
    if tf in v:
        return {"dead": float(v[tf]["dead"]), "hot": float(v[tf]["hot"])}
    if tf.endswith("m"):
        return defaults["15m"]
    if tf.endswith("h"):
        return defaults["1h"]
    if tf.endswith("d"):
        return defaults["1d"]
    return defaults["1h"]


def _atr_pct(df: pd.DataFrame, window: int = 14) -> float:
    """
    Вычисляет ATR% (Average True Range в процентах от цены)
    Используется для оценки волатильности
    """
    df = df[["high", "low", "close"]].copy()
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(window, min_periods=window).mean()
    val = (atr / df["close"]).iloc[-1]
    return float(val) if pd.notna(val) else float("nan")


def _volatility_guard(row, df: pd.DataFrame, timeframe: str, policy: dict):
    """
    Проверяет волатильность и блокирует сигналы при dead/hot волатильности
    Возвращает (allow, reasons, metrics)
    """
    thr = _policy_vol_thr(policy, timeframe)
    try:
        atrp = _atr_pct(df.tail(200))
    except Exception:
        atrp = float("nan")
    if pd.isna(atrp):
        state = "normal"
    else:
        state = "dead" if atrp < thr["dead"] else ("hot" if atrp >= thr["hot"] else "normal")
    metrics = {"atr_pct": atrp, "vol_state": state, "vol_thr_dead": thr["dead"], "vol_thr_hot": thr["hot"]}
    block = bool((policy or {}).get("block_if_dead_volatility", True))
    if block and state == "dead":
        return False, [f"dead_volatility: ATR% {atrp:.2%} < {thr['dead']:.2%}"], metrics
    return True, [], metrics

