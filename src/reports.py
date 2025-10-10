from __future__ import annotations
from pathlib import Path
from typing import Iterable, Tuple, List
import pandas as pd
from sqlalchemy.orm import Session
from src.db import Price, PaperPosition, SignalEvent, SignalOutcome


def _atr_pct(df: pd.DataFrame, window: int = 14) -> float:
    df = df[["high", "low", "close"]].copy()
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(window, min_periods=window).mean()
    val = (atr / df["close"]).iloc[-1]
    return float(val) if pd.notna(val) else float("nan")


def _fetch_tail_prices(db: Session, ex: str, sym: str, tf: str, n: int = 300) -> pd.DataFrame:
    rows = (
        db.query(Price)
        .filter(Price.exchange == ex, Price.symbol == sym, Price.timeframe == tf)
        .order_by(Price.ts.desc())
        .limit(n)
        .all()
    )
    if not rows:
        return pd.DataFrame()
    rows = list(reversed(rows))
    df = pd.DataFrame(
        [{"ts": r.ts, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume} for r in rows]
    )
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts")
    return df


def build_daily_report(db: Session, pairs: Iterable[Tuple[str, str, str]]) -> Path:
    pairs = list(pairs)
    blocks: List[str] = []

    # шапка
    blocks.append(
        """<html><head><meta charset="utf-8">
           <title>Daily Report</title>
           <style>
           body{font-family: ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial,sans-serif;padding:18px;color:#111}
           table{border-collapse:collapse;width:100%;margin:10px 0}
           th,td{border:1px solid #ddd;padding:8px;font-size:14px}
           th{background:#f5f5f5;text-align:left}
           h2{margin:20px 0 10px}
           code{background:#f5f5f5;padding:2px 6px;border-radius:6px}
           .pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px}
           .ok{background:#e8f7ee;color:#0a7d3b}
           .warn{background:#fff6e5;color:#b45309}
           .bad{background:#fde8e8;color:#9b1c1c}
           </style></head><body>
           <h1>Daily Report</h1>"""
    )

    # Позиции
    pos_rows = db.query(PaperPosition).all()
    pos_tbl = []
    for p in pos_rows:
        pos_tbl.append(
            {
                "exchange": p.exchange,
                "symbol": p.symbol,
                "qty": float(p.qty or 0.0),
                "avg_price": float(p.avg_price or 0.0),
                "realized_pnl": float(p.realized_pnl or 0.0),
            }
        )
    df_pos = pd.DataFrame(pos_tbl)
    if df_pos.empty:
        blocks.append("<h2>Positions</h2><p><i>No open positions</i></p>")
    else:
        html_pos = df_pos.to_html(index=False, justify="left")
        blocks.append("<h2>Positions</h2>" + html_pos)

    # Пары — краткая сводка
    rows_summary = []
    for ex, sym, tf in pairs:
        df = _fetch_tail_prices(db, ex, sym, tf, n=400)
        if df.empty:
            rows_summary.append({"exchange": ex, "symbol": sym, "timeframe": tf, "status": "no data"})
            continue
        atrp = _atr_pct(df.tail(200))
        ch = df["close"].pct_change().tail(1).iloc[0]
        rows_summary.append(
            {
                "exchange": ex,
                "symbol": sym,
                "timeframe": tf,
                "last_close": float(df["close"].iloc[-1]),
                "atr_pct": atrp,
                "last_change": ch,
                "status": "ok",
            }
        )
    df_s = pd.DataFrame(rows_summary)
    if not df_s.empty:
        df_s = df_s[["exchange", "symbol", "timeframe", "last_close", "last_change", "atr_pct", "status"]]
        blocks.append("<h2>Market Snapshots</h2>" + df_s.to_html(index=False, float_format=lambda x: f"{x:.4f}"))

    # Последние сигналы
    sig = db.query(SignalEvent).order_by(SignalEvent.bar_dt.desc(), SignalEvent.id.desc()).limit(30).all()
    sig_rows = []
    for s in sig:
        sig_rows.append(
            {
                "bar_dt": s.bar_dt,
                "exchange": s.exchange,
                "symbol": s.symbol,
                "tf": s.timeframe,
                "close": s.close,
                "prob": s.prob_up,
                "thr": s.threshold,
                "signal": s.signal,
            }
        )
    df_sig = pd.DataFrame(sig_rows)
    if not df_sig.empty:
        blocks.append("<h2>Recent Signals</h2>" + df_sig.to_html(index=False))

    # Последние исходы
    outs = db.query(SignalOutcome).order_by(SignalOutcome.id.desc()).limit(30).all()
    out_rows = []
    for o in outs:
        out_rows.append(
            {
                "resolved_at": o.resolved_at,
                "exchange": o.exchange,
                "symbol": o.symbol,
                "tf": o.timeframe,
                "entry": o.entry_price,
                "exit": o.exit_price,
                "ret_h": o.ret_h,
                "mdd": o.max_drawdown,
            }
        )
    df_out = pd.DataFrame(out_rows)
    if not df_out.empty:
        blocks.append("<h2>Outcomes</h2>" + df_out.to_html(index=False))

    blocks.append("</body></html>")

    out_dir = Path("artifacts") / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "latest.html"
    out_path.write_text("\n".join(blocks), encoding="utf-8")
    return out_path
