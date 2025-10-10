from __future__ import annotations
from typing import Dict, List, Literal
from pydantic import BaseModel, Field, ValidationError, model_validator, field_validator, ConfigDict
import re

# ---- Вспомогательные валидации ----

_ALLOWED_TF_RE = re.compile(r"^\d+(?:m|h|d)$", re.IGNORECASE)


class VolThresh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dead: float = Field(..., ge=0.0, le=1.0)
    hot: float = Field(..., gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_relation(self):
        if self.hot <= self.dead:
            raise ValueError("hot must be strictly greater than dead")
        return self


class NewsRadar(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    window_minutes: int = Field(60, ge=5, le=1440)
    lookback_windows: int = Field(6, ge=1, le=96)
    min_new: int = Field(6, ge=1, le=10000)
    min_ratio_vs_prev: float = Field(2.0, ge=0.5, le=100.0)
    min_unique_sources: int = Field(3, ge=1, le=1000)
    min_sentiment_abs: float = Field(0.0, ge=0.0, le=1.0)
    symbols: Dict[str, List[str]] = Field(
        default_factory=lambda: {"BTC/USDT": ["btc", "bitcoin"], "ETH/USDT": ["eth", "ethereum"]}
    )
    cooldown_minutes: int = Field(60, ge=0, le=10080)


class Monitor(BaseModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    timeframe: str = "15m"
    flat_after: float = Field(-0.01, le=0.0)
    partial_at: float = Field(0.03, ge=0.0)
    partial_size: float = Field(0.30, ge=0.0, le=1.0)
    cooldown_minutes: int = Field(60, ge=0, le=10080)
    min_ret_change: float = Field(0.005, ge=0.0, le=1.0)
    types: List[Literal["partial", "flat"]] = Field(default_factory=lambda: ["partial", "flat"])
    only_symbols: List[str] = Field(default_factory=list)
    exclude_symbols: List[str] = Field(default_factory=list)

    @field_validator("timeframe")
    @classmethod
    def _tf_ok(cls, v: str):
        if not _ALLOWED_TF_RE.match(v or ""):
            raise ValueError("timeframe must match like '15m'/'1h'/'4h'/'1d'")
        return v.lower()

    @model_validator(mode="after")
    def _bounds(self):
        if self.partial_at <= 0:
            raise ValueError("partial_at must be > 0")
        if self.flat_after >= 0:
            raise ValueError("flat_after must be < 0")
        inter = set(self.only_symbols) & set(self.exclude_symbols)
        if inter:
            raise ValueError(f"only_symbols and exclude_symbols intersect: {sorted(inter)}")
        return self


class Notify(BaseModel):
    model_config = ConfigDict(extra="allow")

    on_buy: bool = True
    radar: bool = False
    radar_gap: float = Field(0.01, ge=0.0, le=1.0)


class Auto(BaseModel):
    model_config = ConfigDict(extra="allow")

    trade_on_buy: bool = False
    close_on_strong_flat: bool = False


def _default_vols() -> Dict[str, VolThresh]:
    return {
        "15m": VolThresh(dead=0.0025, hot=0.0090),
        "1h": VolThresh(dead=0.0040, hot=0.0150),
        "4h": VolThresh(dead=0.0060, hot=0.0200),
        "1d": VolThresh(dead=0.0100, hot=0.0300),
    }


class Policy(BaseModel):
    model_config = ConfigDict(extra="allow")

    # общая логика
    min_prob_gap: float = Field(0.02, ge=0.0, le=1.0)
    cooldown_minutes: int = Field(90, ge=0, le=10080)
    block_if_dead_volatility: bool = True
    max_open_positions: int = Field(0, ge=0, le=10000)
    buy_fraction: float = Field(0.10, ge=0.0, le=1.0)  # опционально: сколько входить на BUY

    # издержки (bps за сторону)
    fee_bps: float = Field(8.0, ge=0.0, le=10000.0)
    slip_bps: float = Field(5.0, ge=0.0, le=10000.0)

    # разделы
    volatility_thresholds: Dict[str, VolThresh] = Field(default_factory=_default_vols)
    news_radar: NewsRadar = Field(default_factory=NewsRadar)
    monitor: Monitor = Field(default_factory=Monitor)
    notify: Notify = Field(default_factory=Notify)
    auto: Auto = Field(default_factory=Auto)

    @field_validator("volatility_thresholds", mode="before")
    @classmethod
    def _vt_keys_ok(cls, v):
        if v is None:
            return {}
        if not isinstance(v, dict):
            raise TypeError("volatility_thresholds must be a mapping timeframe -> {dead,hot}")
        bad = [k for k in v.keys() if not _ALLOWED_TF_RE.match(str(k) or "")]
        if bad:
            raise ValueError(f"invalid timeframe keys: {bad} (use '15m','1h','4h','1d')")
        # приводим ключи к lower для консистентности
        return {str(k).lower(): val for k, val in v.items()}


# ---- Утилиты: merge + красивое объяснение ошибок ----


def deep_merge(a: dict, b: dict) -> dict:
    out = dict(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def explain_validation_errors(err: ValidationError) -> list[dict]:
    friendly = []
    for e in err.errors():
        loc = ".".join(str(p) for p in e.get("loc", []))
        msg = e.get("msg", "invalid")
        val = e.get("input", None)
        friendly.append({"path": loc, "message": msg, "value": val})
    return friendly
