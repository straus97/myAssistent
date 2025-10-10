"""
Роутер для UI эндпоинтов (HTML summary, equity charts)
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.dependencies import get_db, require_api_key
from src.db import PaperPosition, PaperOrder
from src.trade import paper_get_positions, paper_get_orders


router = APIRouter(prefix="/ui", tags=["UI"])


def _last_close(db: Session, exchange: str, symbol: str, timeframe: str) -> float:
    """Получить последнюю цену закрытия"""
    from src.db import Price
    r = (
        db.query(Price)
        .filter(Price.exchange == exchange, Price.symbol == symbol, Price.timeframe == timeframe)
        .order_by(Price.ts.desc())
        .first()
    )
    return float(r.close) if r else 0.0


@router.get("/summary")
def ui_summary(db: Session = Depends(get_db), _=Depends(require_api_key)):
    """Получить JSON-сводку для UI"""
    try:
        merged = {}
        # БД позиции
        db_pos = db.query(PaperPosition).all()
        for p in db_pos:
            last = _last_close(db, p.exchange, p.symbol, "15m") or float(p.avg_price or 0.0)
            mv = float(p.qty or 0.0) * last
            merged[(p.exchange, p.symbol, "15m")] = {
                "exchange": p.exchange,
                "symbol": p.symbol,
                "timeframe": "15m",
                "qty": float(p.qty or 0.0),
                "avg_price": float(p.avg_price or 0.0),
                "last_price": last,
                "market_value": mv,
                "source": "db",
            }
        # JSON позиции
        for p in paper_get_positions():
            key = (p["exchange"], p["symbol"], p.get("timeframe", "15m"))
            if key in merged:
                continue
            last = _last_close(db, p["exchange"], p["symbol"], p.get("timeframe", "15m")) or float(
                p.get("avg_price", 0.0)
            )
            mv = float(p.get("qty", 0.0)) * last
            merged[key] = {
                "exchange": p["exchange"],
                "symbol": p["symbol"],
                "timeframe": p.get("timeframe", "15m"),
                "qty": float(p.get("qty", 0.0)),
                "avg_price": float(p.get("avg_price", 0.0)),
                "last_price": last,
                "market_value": mv,
                "source": "json",
            }
        positions = list(merged.values())
    except Exception:
        positions = []

    orders_json = paper_get_orders()
    orders_db = []
    try:
        rows = db.query(PaperOrder).order_by(PaperOrder.id.desc()).limit(100).all()
        for r in rows:
            orders_db.append(
                {
                    "id": r.id,
                    "created_at": r.created_at,
                    "exchange": r.exchange,
                    "symbol": r.symbol,
                    "side": r.side,
                    "qty": float(r.qty),
                    "price": float(r.price),
                    "fee": float(r.fee),
                    "status": r.status,
                    "note": r.note,
                }
            )
    except Exception:
        pass

    # Сигналы
    from src.routers.signals import signals_recent
    sig = signals_recent(limit=30, db=db)

    # News Radar (упрощённо)
    radar_alerts = []

    return {
        "positions": positions,
        "orders_json": orders_json,
        "orders_db": orders_db,
        "signals": sig,
        "radar_alerts": radar_alerts,
    }


@router.get("/summary_html", response_class=HTMLResponse)
def ui_summary_html(db: Session = Depends(get_db)):
    """Получить HTML-сводку для UI"""
    html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MyAssistant — Summary</title>
  <style>
    body { font: 14px/1.4 -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; margin: 24px; color:#111;}
    h1 { font-size: 20px; margin: 0 0 16px;}
    .grid { display: grid; grid-template-columns: 1fr; gap: 24px; }
    @media (min-width: 1100px) { .grid { grid-template-columns: 1fr 1fr; } }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
    th { background: #f8fafc; font-weight: 600; }
    .pos-green { color: #0a7f2e; font-weight: 600; }
    .pos-red { color: #b91c1c; font-weight: 600; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .pill { display:inline-block; padding:2px 6px; border-radius:999px; background:#eef2ff; }
    .small { font-size: 12px; color:#4b5563; }
  </style>
</head>
<body>
  <h1>📊 MyAssistant — Summary</h1>
  <div id="time" class="small"></div>
  <div class="grid">
    <section>
      <h2>Открытые позиции</h2>
      <div id="positions">Загрузка…</div>
    </section>
    <section>
      <h2>Свежие сигналы</h2>
      <div id="signals">Загрузка…</div>
    </section>
    <section>
      <h2>Ордеры (DB)</h2>
      <div id="orders_db">Загрузка…</div>
    </section>
    <section>
      <h2>News Radar</h2>
      <div id="radar">Загрузка…</div>
    </section>
  </div>

<script>
let CAPS = { can_short:true, can_cover:true, buy_usd:100 };
const ALLOWED_EXCHANGES = ['bybit'];

function fmt(x){ return (x>=0?'+':'') + x.toFixed(2); }

async function load(){
  const apiKey = localStorage.getItem('api_key') || '';
  const r = await fetch('/ui/summary', { headers: {'X-API-Key': apiKey} });
  const d = await r.json();

  // Позиции
  const positions = d.positions || [];
  let total_mv = 0;
  let html_pos = positions.length ? '<table><tr><th>Пара</th><th>Qty</th><th>Avg</th><th>Last</th><th>MV</th><th>PnL%</th></tr>' : '<p>Нет позиций</p>';
  positions.forEach(p => {
    const pnl_pct = (p.last_price / p.avg_price - 1) * 100;
    const cls = pnl_pct >= 0 ? 'pos-green' : 'pos-red';
    html_pos += `<tr>
      <td>${p.symbol}</td>
      <td>${p.qty.toFixed(4)}</td>
      <td>${p.avg_price.toFixed(2)}</td>
      <td>${p.last_price.toFixed(2)}</td>
      <td>${p.market_value.toFixed(2)}</td>
      <td class="${cls}">${pnl_pct.toFixed(2)}%</td>
    </tr>`;
    total_mv += p.market_value;
  });
  if (positions.length) html_pos += '</table>';
  html_pos += `<p class="small">Total MV: ${total_mv.toFixed(2)} USDT</p>`;
  document.getElementById('positions').innerHTML = html_pos;

  // Сигналы
  const signals = (d.signals && d.signals.data) || [];
  let html_sig = signals.length ? '<table><tr><th>Time</th><th>Pair</th><th>Signal</th><th>Prob</th></tr>' : '<p>Нет сигналов</p>';
  signals.slice(0, 10).forEach(s => {
    const dt = new Date(s.bar_dt).toLocaleString('ru-RU', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
    html_sig += `<tr><td class="small">${dt}</td><td>${s.symbol}</td><td><span class="pill">${s.signal}</span></td><td>${(s.prob_up||0).toFixed(3)}</td></tr>`;
  });
  if (signals.length) html_sig += '</table>';
  document.getElementById('signals').innerHTML = html_sig;

  // Ордеры DB
  const orders_db = d.orders_db || [];
  let html_ord = orders_db.length ? '<table><tr><th>ID</th><th>Time</th><th>Pair</th><th>Side</th><th>Qty</th><th>Price</th></tr>' : '<p>Нет ордеров</p>';
  orders_db.slice(0, 10).forEach(o => {
    const dt = new Date(o.created_at).toLocaleString('ru-RU', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
    html_ord += `<tr><td>${o.id}</td><td class="small">${dt}</td><td>${o.symbol}</td><td>${o.side}</td><td>${o.qty.toFixed(4)}</td><td>${o.price.toFixed(2)}</td></tr>`;
  });
  if (orders_db.length) html_ord += '</table>';
  document.getElementById('orders_db').innerHTML = html_ord;

  // News Radar
  const alerts = d.radar_alerts || [];
  let html_radar = alerts.length ? '<ul>' : '<p>Нет алертов</p>';
  alerts.forEach(a => {
    html_radar += `<li><strong>${a.keyword}</strong>: ${a.count} новостей (${a.ratio.toFixed(1)}x)</li>`;
  });
  if (alerts.length) html_radar += '</ul>';
  document.getElementById('radar').innerHTML = html_radar;

  document.getElementById('time').textContent = 'Обновлено: ' + new Date().toLocaleTimeString('ru-RU');
}

if (!localStorage.getItem('api_key')) {
  const k = prompt('Введите X-API-Key (будет сохранён локально):') || '';
  localStorage.setItem('api_key', k);
}

load();
setInterval(load, 30000); // Обновление каждые 30 сек
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/equity_html", response_class=HTMLResponse)
def ui_equity_html(db: Session = Depends(get_db)):
    """Получить HTML-график equity"""
    html = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MyAssistant — Equity</title>
  <style>
    body { font:14px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; margin:24px; color:#111; }
    h1 { margin:0 0 12px; font-size:20px; }
    .row { display:flex; gap:16px; align-items:center; flex-wrap:wrap; margin-bottom:12px;}
    label { color:#374151; }
    input, select { padding:6px 8px; border:1px solid #e5e7eb; border-radius:8px; }
    .small { color:#6b7280; font-size:12px; }
    #chart { width:100%; height:380px; border:1px solid #e5e7eb; border-radius:12px; }
    .pill { display:inline-block; padding:2px 8px; border-radius:999px; background:#f3f4f6; margin-right:8px;}
  </style>
</head>
<body>
  <h1>📈 Equity / PnL</h1>
  <div class="row">
    <label>Limit:
      <input id="limit" type="number" min="10" max="5000" value="500">
    </label>
    <button id="go">Update</button>
    <span id="meta" class="small"></span>
  </div>

  <div id="stats" class="row"></div>
  <canvas id="chart"></canvas>

<script>
const H = 380;

function fmtPct(x){ return (x*100).toFixed(2) + '%'; }
function fmtUsd(x){ return (x>=0?'+':'') + x.toFixed(2) + ' USDT'; }

function drawChart(points) {
  const c = document.getElementById('chart');
  const pr = window.devicePixelRatio || 1;
  const W = c.clientWidth, Hh = c.clientHeight;
  c.width = W * pr; c.height = Hh * pr;
  const g = c.getContext('2d');
  g.scale(pr, pr);
  g.clearRect(0,0,W,Hh);
  if (!points.length) return;

  const xs = points.map(p => new Date(p.ts).getTime());
  const ys = points.map(p => p.equity);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = 16;
  function X(i){ return pad + (W-2*pad) * (xs[i]-xs[0]) / (xs[xs.length-1]-xs[0] || 1); }
  function Y(v){ return (Hh-pad) - (Hh-2*pad) * ((v - minY) / ((maxY-minY)||1)); }

  // grid
  g.strokeStyle = '#e5e7eb'; g.lineWidth = 1;
  for (let k=0;k<5;k++){
    const y = pad + (Hh-2*pad) * k/4;
    g.beginPath(); g.moveTo(pad,y); g.lineTo(W-pad,y); g.stroke();
  }

  // line
  g.strokeStyle = '#111827'; g.lineWidth = 2; g.beginPath();
  g.moveTo(X(0), Y(ys[0]));
  for (let i=1;i<ys.length;i++) g.lineTo(X(i), Y(ys[i]));
  g.stroke();

  // last label
  g.fillStyle = '#111827';
  g.fillText(ys[ys.length-1].toFixed(2), W - pad - 60, pad + 12);
}

async function load(){
  const limit = parseInt(document.getElementById('limit').value || '500', 10);
  const apiKey = localStorage.getItem('api_key') || '';
  const r = await fetch(`/trade/equity/history?limit=${limit}`, {
    headers: { 'X-API-Key': apiKey }
  });
  const j = await r.json();
  if (j.status !== 'ok') { alert('error'); return; }

  const hist = j.history || [];
  document.getElementById('meta').textContent = `Points: ${hist.length}`;
  drawChart(hist);

  // Простая статистика
  if (hist.length > 1) {
    const first = hist[0].equity;
    const last = hist[hist.length - 1].equity;
    const pnl = last - first;
    const pct = (pnl / first) * 100;
    document.getElementById('stats').innerHTML = `
      <span class="pill">Start: ${first.toFixed(2)}</span>
      <span class="pill">Current: ${last.toFixed(2)}</span>
      <span class="pill">PnL: ${fmtUsd(pnl)} (${fmtPct(pct/100)})</span>
    `;
  }
}

if (!localStorage.getItem('api_key')) {
  const k = prompt('Введите X-API-Key (будет сохранён локально в браузере):') || '';
  localStorage.setItem('api_key', k);
}
document.getElementById('go').onclick = load;
window.addEventListener('resize', load);
load();
</script>
</body>
</html>
"""
    return HTMLResponse(html)
