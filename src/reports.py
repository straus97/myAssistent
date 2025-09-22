# src/reports.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
import html
import pandas as pd
from sqlalchemy.orm import Session

from .db import Article, ArticleAnnotation
from .features import load_prices_df

# Сколько баров в сутках для разных таймфреймов
MIN_PER_BAR = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440}

def _bars_per_day(timeframe: str) -> int:
    m = MIN_PER_BAR.get(timeframe, 60)
    return max(1, (24 * 60) // m)

def _collect_news_last_24h(db: Session) -> List[Tuple[Article, ArticleAnnotation]]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=24)
    rows = (
        db.query(Article, ArticleAnnotation)
        .join(ArticleAnnotation, ArticleAnnotation.article_id == Article.id)
        .filter(Article.published_at != None)
        .all()
    )
    out = []
    for art, ann in rows:
        dt = art.published_at
        if dt is None:
            continue
        # к UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        if dt >= since:
            out.append((art, ann))
    return out

def _summarize_tags(pairs: List[Tuple[Article, ArticleAnnotation]]) -> List[Tuple[str, int]]:
    from collections import Counter
    c = Counter()
    for _, ann in pairs:
        if ann.tags:
            for t in ann.tags.split(","):
                t = t.strip().lower()
                if t:
                    c[t] += 1
    return sorted(c.items(), key=lambda x: (-x[1], x[0]))

def _price_section(db: Session, exchange: str, symbol: str, timeframe: str) -> Dict:
    df = load_prices_df(db, exchange, symbol, timeframe)
    if df.empty:
        return {"exchange": exchange, "symbol": symbol, "timeframe": timeframe, "status": "no_data"}
    last_close = float(df["close"].iloc[-1])
    bars = _bars_per_day(timeframe)
    if len(df) > bars:
        prev = float(df["close"].iloc[-bars])
        ret_24h = (last_close / prev) - 1.0
    else:
        ret_24h = None
    return {
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "last_dt": df.index[-1].strftime("%Y-%m-%d %H:%M UTC"),
        "last_close": last_close,
        "ret_24h": ret_24h,
        "status": "ok"
    }

def build_daily_report(
    db: Session,
    pairs: List[Tuple[str, str, str]],  # [(exchange, symbol, timeframe), ...]
    out_dir: Path | None = None
) -> Path:
    """
    Строит HTML-отчёт за последние 24 часа по новостям и ценам.
    Возвращает путь к созданному файлу.
    """
    out_dir = out_dir or Path("artifacts") / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Новости
    recent = _collect_news_last_24h(db)
    tag_stats = _summarize_tags(recent)
    top_pos = sorted(recent, key=lambda x: (x[1].sentiment or 0), reverse=True)[:5]
    top_neg = sorted(recent, key=lambda x: (x[1].sentiment or 0))[:5]

    # Цены
    price_blocks = [_price_section(db, ex, sym, tf) for (ex, sym, tf) in pairs]

    # HTML
    now = datetime.now(timezone.utc)
    title = f"Ежедневный отчёт — {now.strftime('%Y-%m-%d %H:%M UTC')}"
    css = """
    <style>
      body{font-family:Segoe UI,Arial,sans-serif; margin:24px; color:#222;}
      h1{margin:0 0 8px}
      .muted{color:#666; font-size:12px}
      .grid{display:grid; gap:16px}
      .cards{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}
      .card{border:1px solid #ddd; border-radius:12px; padding:12px}
      table{width:100%; border-collapse:collapse; font-size:14px}
      th,td{border-bottom:1px solid #eee; padding:6px 8px; text-align:left; vertical-align:top}
      .pos{color:#0a8f3c; font-weight:600}
      .neg{color:#c62828; font-weight:600}
      .tag{display:inline-block; background:#f1f3f5; border-radius:8px; padding:2px 8px; margin:2px; font-size:12px}
      .kpi{font-size:18px; font-weight:600}
      .small{font-size:12px; color:#666}
    </style>
    """

    def fmt_pct(x):
        if x is None: return "—"
        return f"{x*100:+.2f}%"

    # Блок цен
    price_html = ""
    for pb in price_blocks:
        if pb["status"] != "ok":
            price_html += f"<div class='card'><div class='kpi'>{pb['exchange']} {pb['symbol']} {pb['timeframe']}</div><div class='small'>Нет данных</div></div>"
            continue
        price_html += (
            "<div class='card'>"
            f"<div class='kpi'>{pb['exchange']} · {pb['symbol']} · {pb['timeframe']}</div>"
            f"<div class='small'>Последняя свеча: {pb['last_dt']}</div>"
            f"<div>Цена: <b>{pb['last_close']:.2f}</b> · 24h: <span class='{('pos' if (pb['ret_24h'] or 0)>0 else 'neg')}'>{fmt_pct(pb['ret_24h'])}</span></div>"
            "</div>"
        )

    # Топ новости
    def news_rows(items, cls):
        rows = ""
        for art, ann in items:
            tags = ", ".join((ann.tags or "").split(",")) if ann.tags else ""
            rows += (
                "<tr>"
                f"<td class='{cls}'>{ann.sentiment if ann.sentiment is not None else 0:.2f}</td>"
                f"<td><a href='{html.escape(art.url)}' target='_blank'>{html.escape(art.title)}</a><br>"
                f"<span class='small'>{html.escape(art.source or '')}</span></td>"
                f"<td>{html.escape(tags)}</td>"
                "</tr>"
            )
        return rows or "<tr><td colspan='3' class='small'>Нет данных</td></tr>"

    top_pos_html = "<table><thead><tr><th>Sent</th><th>Заголовок</th><th>Теги</th></tr></thead><tbody>"
    top_pos_html += news_rows(top_pos, "pos") + "</tbody></table>"

    top_neg_html = "<table><thead><tr><th>Sent</th><th>Заголовок</th><th>Теги</th></tr></thead><tbody>"
    top_neg_html += news_rows(top_neg, "neg") + "</tbody></table>"

    # Теги
    tags_html = "<table><thead><tr><th>Тег</th><th>Кол-во</th></tr></thead><tbody>"
    if tag_stats:
        for name, cnt in tag_stats[:15]:
            tags_html += f"<tr><td><span class='tag'>{html.escape(name)}</span></td><td>{cnt}</td></tr>"
    else:
        tags_html += "<tr><td colspan='2' class='small'>Нет данных за 24ч</td></tr>"
    tags_html += "</tbody></table>"

    html_doc = f"""
    <html><head><meta charset="utf-8"/>{css}<title>{html.escape(title)}</title></head>
    <body>
      <h1>{html.escape(title)}</h1>
      <div class="muted">Автогенерация отчёта на основе локальной БД (новости+цены). Это исследовательская сводка.</div>
      <h2>Рынок (ключевые пары)</h2>
      <div class="grid cards">{price_html}</div>
      <h2>Топ позитивных новостей</h2>
      <div class="card">{top_pos_html}</div>
      <h2>Топ негативных новостей</h2>
      <div class="card">{top_neg_html}</div>
      <h2>Частые теги за 24ч</h2>
      <div class="card">{tags_html}</div>
    </body></html>
    """

    ts = now.strftime("%Y%m%d_%H%M")
    out_path = out_dir / f"daily_{ts}.html"
    out_path.write_text(html_doc, encoding="utf-8")
    # делаем «ярлык» на последний отчёт
    (out_dir / "latest.html").write_text(html_doc, encoding="utf-8")
    return out_path
