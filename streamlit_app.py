# streamlit_app.py
import json
from pathlib import Path
from src.config import settings
import pandas as pd
import requests
import streamlit as st
from src.logging_setup import setup_logging
import os

logger = setup_logging("streamlit")
logger.info("UI started")

API = settings.API_BASE_URL
API_KEY = os.getenv("API_KEY") or ""
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

st.set_page_config(page_title="My Assistant Dashboard", layout="wide")
st.title("🧠 My Assistant — Dashboard")

# ---- SIDEBAR ----
st.sidebar.header("Параметры")
exchange = st.sidebar.selectbox("Биржа", ["bybit", "binance"])
symbol = st.sidebar.selectbox("Пара", ["BTC/USDT", "ETH/USDT"])
timeframe = st.sidebar.selectbox("Таймфрейм", ["15m", "1h", "4h", "1d"])
limit_bars = st.sidebar.slider("Сколько свечей загрузить", 200, 2000, 500, step=100)

# Горизонт для таргета (в барах)
default_hor = 6 if timeframe in ("1h", "4h", "1d") else 12  # для 15m ~= 3 часа
horizon_steps = st.sidebar.number_input("Горизонт предсказания (в барах)", 1, 200, default_hor, step=1)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Automation (/automation/run)")
def run_job(payload: dict, ok_msg: str):
    try:
        r = requests.post(f"{API}/automation/run", json=payload, headers=HEADERS, timeout=120)
        # сервер может вернуть текст/JSON — покажем как есть
        try:
            st.sidebar.success(f"{ok_msg}: {r.json()}")
        except Exception:
            st.sidebar.success(f"{ok_msg}: {r.status_code} {r.text[:400]}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")

st.sidebar.markdown("---")
if st.sidebar.button("Разовая оценка + уведомить"):
    payload = {
        "action": "signal_once",
        "exchange": exchange,
        "symbol": symbol,
        "timeframe": timeframe,
        "horizon_steps": int(horizon_steps),
        "notify": True   # просим прислать в ТГ
    }
    try:
        r = requests.post(f"{API}/automation/run", json=payload, headers=HEADERS, timeout=60)
        # покажем, что вернул сервер
        try:
            st.sidebar.success(f"signal_once: {r.json()}")
        except Exception:
            st.sidebar.success(f"signal_once: {r.status_code} {r.text[:400]}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")

if st.sidebar.button("Пройтись по watchlist"):
    run_job({ "action": "scan_watchlist" }, "scan_watchlist")

if st.sidebar.button("Вытянуть цены по watchlist"):
    run_job({ "job": "fetch_prices" }, "fetch_prices")

if st.sidebar.button("Подтянуть новости (Automation)"):
    run_job({ "job": "fetch_news" }, "fetch_news")

if st.sidebar.button("Проанализировать новости (Automation)"):
    run_job({ "job": "analyze_news" }, "analyze_news")

if st.sidebar.button("Потренировать модели (Automation)"):
    run_job({ "job": "train_models" }, "train_models")

if st.sidebar.button("Сделать сигналы"):
    run_job({ "job": "make_signals" }, "make_signals")

if st.sidebar.button("News Radar"):
    run_job({ "job": "news_radar" }, "news_radar")

st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Telegram уведомления")

tg_token = st.sidebar.text_input("Bot token", value=settings.TELEGRAM_BOT_TOKEN or "", type="password")
tg_chat  = st.sidebar.text_input("Chat ID", value=settings.TELEGRAM_CHAT_ID or "")
tg_enabled = st.sidebar.checkbox("Включить", value=bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID))

col_tg1, col_tg2 = st.sidebar.columns(2)
if col_tg1.button("Сохранить /notify/config"):
    body = {"enabled": tg_enabled, "telegram_token": tg_token, "telegram_chat_id": tg_chat}
    try:
        r = requests.post(f"{API}/notify/config", json=body, headers=HEADERS, timeout=30)
        st.sidebar.success(f"/notify/config => {r.status_code}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")

if col_tg2.button("Тест /notify/test"):
    try:
        r = requests.post(f"{API}/notify/test", headers=HEADERS, timeout=30)
        st.sidebar.success(r.json())
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")


if st.sidebar.button("📥 Подтянуть новости (RSS)"):
    try:
        r = requests.post(f"{API}/news/fetch", headers=HEADERS, timeout=60)
        st.sidebar.success(f"Новости: добавлено +{r.json().get('added')}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")
    logger.info("Нажал Подтянуть новости (RSS)")

if st.sidebar.button("🧪 Проанализировать новости"):
    try:
        r = requests.post(f"{API}/news/analyze", headers=HEADERS, timeout=60)
        st.sidebar.success(f"Аналитика новостей: обработано {r.json().get('processed')}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")
    logger.info("Нажал Проанализировать новости")

if st.sidebar.button("💹 Подтянуть цены (OHLCV)"):
    try:
        r = requests.post(f"{API}/prices/fetch", json={
            "exchange": exchange, "symbol": symbol, "timeframe": timeframe, "limit": limit_bars
        }, headers=HEADERS, timeout=120)
        st.sidebar.success(f"Цены: добавлено +{r.json().get('added')}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")
    logger.info("Нажал Подтянуть цены (OHLCV)")

st.sidebar.markdown("---")
if st.sidebar.button("🧱 Сформировать датасет"):
    try:
        r = requests.post(f"{API}/dataset/build", json={
            "exchange": exchange, "symbol": symbol, "timeframe": timeframe, "horizon_steps": int(horizon_steps)
        }, headers=HEADERS, timeout=120)
        st.sidebar.success(f"OK: {r.json().get('info')}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")
    logger.info("Нажал Сформировать датасет")

if st.sidebar.button("🎯 Обучить модель"):
    try:
        r = requests.post(f"{API}/model/train", json={
            "exchange": exchange, "symbol": symbol, "timeframe": timeframe, "horizon_steps": int(horizon_steps)
        }, headers=HEADERS, timeout=300)
        st.sidebar.success(f"Метрики: {r.json().get('metrics')}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")
    logger.info("Нажал Обучить модель")

st.sidebar.markdown("---")
if st.sidebar.button("📑 Построить ежедневный отчёт"):
    try:
        r = requests.post(f"{API}/report/daily", headers=HEADERS, timeout=120)
        st.sidebar.success(f"OK: {r.json().get('path')}")
    except Exception as e:
        st.sidebar.error(f"Ошибка: {e}")
    logger.info("Нажал Построить ежедневный отчёт")

# ---- MAIN LAYOUT ----
col1, col2 = st.columns([2, 1])

# 1) График цены
with col1:
    st.subheader(f"График {exchange} · {symbol} · {timeframe}")
    try:
        rr = requests.get(f"{API}/prices/latest", params={
            "exchange": exchange, "symbol": symbol, "timeframe": timeframe, "limit": 500
        }, headers=HEADERS, timeout=60)
        data = rr.json()
        if isinstance(data, dict) and data.get("status") == "error":
            st.warning(data.get("detail"))
        else:
            df = pd.DataFrame(data)
            if not df.empty:
                df["dt"] = pd.to_datetime(df["ts"], unit="ms")
                df = df.set_index("dt")
                st.line_chart(df["close"])
            else:
                st.info("Нет данных по ценам. Нажми «Подтянуть цены».")
    except Exception as e:
        st.error(f"Ошибка запроса цен: {e}")

# 2) Метрики последнего обучения
with col2:
    st.subheader("Метрики последней тренировки")
    metrics_path = Path(settings.ARTIFACTS_DIR) / "metrics.json"
    if metrics_path.exists():
        try:
            m = json.loads(metrics_path.read_text(encoding="utf-8"))
            st.metric("accuracy", f"{m.get('accuracy', 0):.3f}")
            if m.get("roc_auc") is not None:
                st.metric("roc_auc", f"{m['roc_auc']:.3f}")
            st.metric("total_return", f"{m.get('total_return', 0):.2%}")
            if m.get("sharpe_like") is not None:
                st.metric("sharpe_like", f"{m['sharpe_like']:.2f}")
            st.caption(f"train={m.get('n_train')}, test={m.get('n_test')}, thr={m.get('threshold')}")
        except Exception as e:
            st.error(f"Не удалось прочитать metrics.json: {e}")
    else:
        st.info("Ещё нет метрик. Нажми «Обучить модель».")

st.markdown("---")

# 3) Последние аннотированные новости
st.subheader("Аннотированные новости (последние)")
try:
    rr = requests.get(f"{API}/news/annotated", params={"limit": 50}, headers=HEADERS, timeout=60)
    rows = rr.json()
    if isinstance(rows, list) and rows:
        df_news = pd.DataFrame(rows)
        show_cols = ["published_at", "source", "title", "lang", "sentiment", "tags", "url"]
        for c in show_cols:
            if c not in df_news.columns: df_news[c] = None
        st.dataframe(df_news[show_cols], width="stretch", hide_index=True)   # ← вот тут
    else:
        st.info("Пока нет аннотированных новостей. Нажми «Подтянуть новости» и «Проанализировать новости».")
except Exception as e:
    st.error(f"Ошибка загрузки новостей: {e}")

st.markdown("---")
st.subheader("История обучений (последние)")
try:
    rr = requests.get(f"{API}/model/runs", params={"limit": 20}, headers=HEADERS, timeout=60)
    runs = rr.json()
    if isinstance(runs, list) and runs:
        df_runs = pd.DataFrame(runs)
        show_cols = ["created_at","exchange","symbol","timeframe","horizon_steps",
                     "n_train","n_test","accuracy","roc_auc","threshold","total_return","sharpe_like","model_path"]
        for c in show_cols:
            if c not in df_runs.columns: df_runs[c] = None
        st.dataframe(df_runs[show_cols], width="stretch", hide_index=True)   # ← и тут
    else:
        st.info("Пока нет сохранённых запусков. Нажми «Обучить модель».")
except Exception as e:
    st.error(f"Ошибка загрузки истории: {e}")

# 4) Встроенный последний отчёт
st.subheader("Последний отчёт (latest.html)")
report_url = f"{API}/report/latest"
st.components.v1.iframe(src=report_url, height=800, scrolling=True)

@st.cache_data(ttl=60)
def get_latest_prices(api, exchange, symbol, timeframe, limit=500):
    r = requests.get(f"{api}/prices/latest", params={
        "exchange": exchange, "symbol": symbol, "timeframe": timeframe, "limit": limit
    }, timeout=60)
    return r.json()

data = get_latest_prices(API, exchange, symbol, timeframe, 500)
