# 📚 API Документация MyAssistent

> **Версия:** 0.8  
> **Base URL:** `http://127.0.0.1:8000`  
> **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## 🔐 Авторизация

Все эндпоинты требуют заголовок **`X-API-Key`**, кроме:
- `/` (redirect)
- `/ping`
- `/docs`, `/redoc`
- HTML-панели (`/ui/*`)

### Пример запроса

```bash
curl -X GET "http://127.0.0.1:8000/news/latest" \
  -H "X-API-Key: your-api-key-here"
```

### Формат ответов

**Успешный ответ:**
```json
{
  "status": "ok",
  "data": [...],
  "message": "optional message"
}
```

**Ошибка:**
```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "detail": "Error description"
}
```

---

## 📑 Группы Эндпоинтов

- [Новости (News)](#-новости-news)
- [Цены (Prices)](#-цены-prices)
- [Датасет (Dataset)](#-датасет-dataset)
- [Модели (Models)](#-модели-models)
- [Сигналы (Signals)](#-сигналы-signals)
- [Риск-Менеджмент (Risk)](#-риск-менеджмент-risk)
- [Уведомления (Notify)](#-уведомления-notify)
- [Торговля (Trade)](#-торговля-trade)
- [Автоматизация (Automation)](#-автоматизация-automation)
- [Watchlist](#-watchlist)
- [Отчёты (Report)](#-отчёты-report)
- [UI Панели](#-ui-панели)
- [Журнал (Journal)](#-журнал-journal)
- [Резервное копирование (Backup)](#-резервное-копирование-backup)
- [База данных (DB Admin)](#-база-данных-db-admin)
- [Debug](#-debug)

---

## 📰 Новости (News)

### `POST /news/fetch`

Загружает RSS-ленты новостей из источников.

**Query Parameters:**
- `sources` (optional, default: все) — список источников через запятую

**Response:**
```json
{
  "status": "ok",
  "total_fetched": 15,
  "sources": ["cointelegraph", "coindesk"]
}
```

---

### `POST /news/analyze`

Анализирует новости (sentiment, теги) для статей без аннотаций.

**Response:**
```json
{
  "status": "ok",
  "analyzed": 10,
  "message": "Analyzed 10 articles"
}
```

---

### `GET /news/latest`

Возвращает последние новости.

**Query Parameters:**
- `limit` (default: 20) — количество статей
- `source` (optional) — фильтр по источнику

**Response:**
```json
{
  "status": "ok",
  "data": [
    {
      "id": 1,
      "title": "Bitcoin breaks $50k",
      "url": "https://...",
      "source": "cointelegraph",
      "published_at": "2023-10-10T12:00:00Z",
      "sentiment": 0.8,
      "tags": "btc bullish"
    }
  ]
}
```

---

### `GET /news/search`

Поиск новостей по тексту.

**Query Parameters:**
- `q` (required) — поисковый запрос
- `limit` (default: 20)

**Response:** аналогичен `/news/latest`

---

### `GET /news/radar`

Детектор всплесков новостей (News Radar).

**Query Parameters:**
- `symbol` (default: `BTC/USDT`) — торговая пара
- `min_ratio` (default: 2.0) — минимальное отношение к предыдущему окну

**Response:**
```json
{
  "status": "ok",
  "alert": true,
  "symbol": "BTC/USDT",
  "current_count": 12,
  "prev_avg": 4.5,
  "ratio": 2.67,
  "unique_sources": 5,
  "avg_sentiment": 0.3
}
```

---

## 💹 Цены (Prices)

### `POST /prices/fetch`

Загружает OHLCV данные с биржи.

**Query Parameters:**
- `exchange` (default: `bybit`) — биржа
- `symbol` (default: `BTC/USDT`) — торговая пара
- `timeframe` (default: `1h`) — таймфрейм (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`)
- `limit` (default: 500) — количество свечей

**Response:**
```json
{
  "status": "ok",
  "stored": 500,
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h"
}
```

---

### `GET /prices/latest`

Возвращает последние свечи.

**Query Parameters:**
- `exchange` (default: `bybit`)
- `symbol` (default: `BTC/USDT`)
- `timeframe` (default: `1h`)
- `limit` (default: 100)

**Response:**
```json
{
  "status": "ok",
  "data": [
    {
      "ts": 1696939200000,
      "dt": "2023-10-10T12:00:00Z",
      "open": 49500.0,
      "high": 50100.0,
      "low": 49300.0,
      "close": 50000.0,
      "volume": 1234.56
    }
  ]
}
```

---

## 🗂️ Датасет (Dataset)

### `POST /dataset/build`

Строит датасет с фичами для ML (RSI, BB, новости, etc.).

**Query Parameters:**
- `exchange` (default: `bybit`)
- `symbol` (default: `BTC/USDT`)
- `timeframe` (default: `1h`)
- `horizon_steps` (default: 6) — горизонт прогноза

**Response:**
```json
{
  "status": "ok",
  "n_rows": 1500,
  "n_features": 40,
  "features": ["ret_1", "ret_3", "rsi_14", "bb_pct_20_2", "news_cnt_6", ...],
  "preview": "artifacts/dataset_preview.csv"
}
```

---

## 🤖 Модели (Models)

### `POST /model/train`

Обучает XGBoost модель на датасете.

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "horizon_steps": 6,
  "test_ratio": 0.2
}
```

**Response:**
```json
{
  "status": "ok",
  "model_path": "artifacts/models/xgb_20231010_120000.pkl",
  "metrics": {
    "n_train": 1200,
    "n_test": 300,
    "accuracy": 0.58,
    "roc_auc": 0.62,
    "total_return": 0.15,
    "sharpe_like": 1.8,
    "threshold": 0.56
  }
}
```

---

### `POST /model/train_missing`

Умная дотренировка моделей по SLA (max_age_days, retrain_if_auc_below).

**Response:**
```json
{
  "status": "ok",
  "trained": [
    {"symbol": "BTC/USDT", "timeframe": "1h", "reason": "stale (age=8 days)"}
  ],
  "skipped": 2
}
```

---

### `GET /model/health`

Проверяет свежесть моделей для watchlist.

**Response:**
```json
{
  "status": "ok",
  "data": [
    {
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "age_days": 2.5,
      "fresh": true,
      "auc": 0.65
    }
  ]
}
```

---

### `GET /model/active`

Возвращает активные модели (реестр).

**Response:**
```json
{
  "status": "ok",
  "data": {
    "bybit:BTC/USDT:1h:6": "artifacts/models/xgb_20231008_030000.pkl"
  }
}
```

---

### `POST /model/active`

Устанавливает активную модель для пары.

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "horizon_steps": 6,
  "model_path": "artifacts/models/xgb_20231010_120000.pkl"
}
```

---

### `POST /model/champion/promote_if_better`

Champion/Challenger отбор: обучает новую модель и промоутит, если лучше.

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "horizon_steps": 6
}
```

**Response:**
```json
{
  "status": "ok",
  "promoted": true,
  "reason": "Sharpe improved: 1.2 → 1.5",
  "new_champion": "artifacts/models/xgb_20231010_120000.pkl"
}
```

---

### `POST /model/walk_forward_cv`

Запускает Walk-Forward Cross-Validation.

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "window_train": 1200,
  "window_test": 200,
  "step": 100
}
```

**Response:**
```json
{
  "status": "ok",
  "folds": [
    {
      "start": "2023-01-01T00:00:00Z",
      "end": "2023-02-15T00:00:00Z",
      "accuracy": 0.57,
      "roc_auc": 0.61,
      "sharpe_like": 1.3
    }
  ],
  "summary": {
    "n_folds": 5,
    "auc_mean": 0.62,
    "sharpe_mean": 1.4
  }
}
```

---

## 🎯 Сигналы (Signals)

### `POST /signal/latest`

Генерирует торговый сигнал для пары (inference + фильтры + DB + Telegram).

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "horizon_steps": 6,
  "auto_trade": false
}
```

**Response:**
```json
{
  "status": "ok",
  "signal": "BUY",
  "probability": 0.68,
  "bar_dt": "2023-10-10T12:00:00Z",
  "close": 50123.45,
  "filters_passed": true,
  "vol_state": "normal",
  "event_id": 123
}
```

---

### `GET /signals/recent`

Возвращает последние сигналы из БД.

**Query Parameters:**
- `limit` (default: 20)
- `symbol` (optional)

**Response:**
```json
{
  "status": "ok",
  "data": [
    {
      "id": 123,
      "exchange": "bybit",
      "symbol": "BTC/USDT",
      "timeframe": "15m",
      "direction": "BUY",
      "probability": 0.68,
      "created_at": "2023-10-10T12:05:00Z"
    }
  ]
}
```

---

### `GET /signals/outcomes`

Возвращает исходы сигналов (PnL, MDD).

**Query Parameters:**
- `limit` (default: 20)

**Response:**
```json
{
  "status": "ok",
  "data": [
    {
      "signal_id": 120,
      "entry_price": 50000.0,
      "exit_price": 51500.0,
      "ret_h": 0.03,
      "max_drawdown": -0.008,
      "closed_at": "2023-10-10T18:00:00Z"
    }
  ]
}
```

---

## 🛡️ Риск-Менеджмент (Risk)

### `GET /risk/policy`

Возвращает текущую risk policy.

**Response:**
```json
{
  "status": "ok",
  "policy": {
    "min_prob_gap": 0.02,
    "cooldown_minutes": 90,
    "block_if_dead_volatility": true,
    "volatility_thresholds": {
      "15m": {"dead": 0.004, "hot": 0.015}
    },
    "filters": {
      "min_rel_volume": 0.2,
      "max_bar_change": 0.03,
      "require_uptrend": false
    }
  }
}
```

---

### `POST /risk/policy`

Обновляет risk policy.

**Request Body:**
```json
{
  "min_prob_gap": 0.03,
  "cooldown_minutes": 120
}
```

---

## 🔔 Уведомления (Notify)

### `GET /notify/config`

Возвращает конфигурацию уведомлений.

**Response:**
```json
{
  "status": "ok",
  "config": {
    "telegram_token": "123456:ABC...",
    "telegram_chat_id": "-100123456789",
    "on_buy": true,
    "on_sell": true,
    "style": "simple"
  }
}
```

---

### `POST /notify/config`

Обновляет конфигурацию уведомлений.

**Request Body:**
```json
{
  "telegram_chat_id": "-100999888777",
  "on_buy": true
}
```

---

### `POST /notify/test`

Отправляет тестовое уведомление в Telegram.

**Response:**
```json
{
  "status": "ok",
  "sent": true,
  "message_id": 12345
}
```

---

## 💰 Торговля (Trade)

### `GET /trade/positions`

Возвращает открытые позиции (paper trading).

**Response:**
```json
{
  "status": "ok",
  "positions": [
    {
      "exchange": "bybit",
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "qty": 0.15,
      "avg_price": 50000.0
    }
  ]
}
```

---

### `GET /trade/equity`

Возвращает текущий equity (cash + positions).

**Response:**
```json
{
  "status": "ok",
  "cash": 5000.0,
  "positions_value": 7500.0,
  "equity": 12500.0
}
```

---

### `POST /trade/paper/close`

Закрывает позицию по паре.

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "price": 51000.0
}
```

**Response:**
```json
{
  "status": "ok",
  "pnl": 150.0,
  "closed_qty": 0.15
}
```

---

### `POST /trade/manual/buy`

Ручная покупка (paper trading).

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "qty": 0.1,
  "price": 50000.0
}
```

---

### `POST /trade/manual/sell`

Ручная продажа.

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "qty": 0.05,
  "price": 51000.0
}
```

---

### `POST /trade/manual/short`

Открывает шорт (будущая функция).

---

### `POST /trade/manual/cover`

Закрывает шорт (будущая функция).

---

### `GET /trade/guard`

Возвращает состояние Kill Switch.

**Response:**
```json
{
  "status": "ok",
  "mode": "live"
}
```

**Режимы:**
- `live` — торговля разрешена
- `close_only` — только закрытие позиций
- `locked` — торговля заблокирована

---

### `POST /trade/guard`

Устанавливает режим Kill Switch.

**Request Body:**
```json
{
  "mode": "close_only"
}
```

---

## ⚙️ Автоматизация (Automation)

### `GET /automation/status`

Возвращает статус APScheduler jobs.

**Response:**
```json
{
  "status": "ok",
  "jobs": [
    {
      "id": "job_watchlist_discover",
      "next_run": "2023-10-10T18:00:00Z",
      "trigger": "interval: 6 hours"
    },
    {
      "id": "job_prices_sync",
      "next_run": "2023-10-10T12:03:00Z",
      "trigger": "interval: 3 minutes"
    }
  ]
}
```

---

### `POST /automation/run`

Запускает job вручную.

**Request Body:**
```json
{
  "job": "fetch_prices"
}
```

**Доступные jobs:**
- `fetch_news`
- `analyze_news`
- `fetch_prices`
- `train_models`
- `make_signals`
- `daily_report`
- `discover_pairs`

---

## 🎯 Watchlist

### `GET /watchlist`

Возвращает список отслеживаемых пар.

**Response:**
```json
{
  "status": "ok",
  "data": [
    {
      "exchange": "bybit",
      "symbol": "BTC/USDT",
      "timeframe": "1h"
    }
  ]
}
```

---

### `POST /watchlist/add`

Добавляет пару в watchlist.

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "ETH/USDT",
  "timeframe": "15m"
}
```

---

### `POST /watchlist/remove`

Удаляет пару из watchlist.

**Request Body:**
```json
{
  "exchange": "bybit",
  "symbol": "SOL/USDT"
}
```

---

### `POST /watchlist/discover`

Автоматически добавляет топ-ликвидные пары.

**Query Parameters:**
- `min_volume` (default: 50000000) — минимальный объём
- `max_pairs` (default: 25)

**Response:**
```json
{
  "status": "ok",
  "added": 5,
  "pairs": ["DOGE/USDT", "SHIB/USDT", ...]
}
```

---

## 📊 Отчёты (Report)

### `GET /report/daily`

Возвращает ежедневный HTML-отчёт.

**Response:**
```json
{
  "status": "ok",
  "html_path": "artifacts/reports/daily_20231010_0350.html"
}
```

---

### `POST /report/generate`

Генерирует отчёт по требованию.

**Response:**
```json
{
  "status": "ok",
  "report_path": "artifacts/reports/latest.html"
}
```

---

## 🖥️ UI Панели

### `GET /ui/summary`

Возвращает HTML-панель с сводкой (equity, позиции, сигналы).

**Response:** HTML страница

---

### `GET /ui/equity_chart`

Возвращает график equity.

**Response:** HTML страница с встроенным графиком

---

## 📝 Журнал (Journal)

### `GET /journal/export_csv`

Экспортирует журнал сделок в CSV.

**Response:** файл `journal.csv`

---

### `GET /journal/export_xlsx`

Экспортирует журнал в Excel (XLSX) с форматированием.

**Response:** файл `journal.xlsx`

---

## 💾 Резервное копирование (Backup)

### `POST /backup/snapshot`

Создаёт ZIP-снимок (БД + конфиги + модели).

**Response:**
```json
{
  "status": "ok",
  "backup_path": "artifacts/backups/snapshot_20231010_120530.zip",
  "size_mb": 15.2
}
```

---

## 🗄️ База данных (DB Admin)

### `GET /db/stats`

Возвращает статистику БД.

**Response:**
```json
{
  "status": "ok",
  "stats": {
    "articles": 1234,
    "prices": 50000,
    "signals": 345,
    "models_trained": 89
  }
}
```

---

### `POST /db/vacuum`

Оптимизирует БД (VACUUM для SQLite).

---

### `POST /db/clear_old`

Удаляет старые записи.

**Query Parameters:**
- `table` (required) — таблица (`prices`, `articles`, `signals`)
- `days` (default: 90) — хранить последние N дней

---

## 🔧 Debug

### `GET /_debug/info`

Возвращает системную информацию (routes, cwd, sys.path).

**Response:**
```json
{
  "status": "ok",
  "routes": ["/", "/ping", "/news/fetch", ...],
  "cwd": "C:\\AI\\myAssistent",
  "sys_path": ["...", "..."]
}
```

---

### `GET /_debug/env`

Возвращает переменные окружения (замаскированные).

---

## 🎓 Примеры Использования

### Полный цикл сигнала

```bash
# 1. Загрузить цены
curl -X POST "http://127.0.0.1:8000/prices/fetch?symbol=BTC/USDT&timeframe=1h" \
  -H "X-API-Key: YOUR_KEY"

# 2. Загрузить новости
curl -X POST "http://127.0.0.1:8000/news/fetch" \
  -H "X-API-Key: YOUR_KEY"

# 3. Проанализировать новости
curl -X POST "http://127.0.0.1:8000/news/analyze" \
  -H "X-API-Key: YOUR_KEY"

# 4. Построить датасет
curl -X POST "http://127.0.0.1:8000/dataset/build?symbol=BTC/USDT&timeframe=1h" \
  -H "X-API-Key: YOUR_KEY"

# 5. Обучить модель
curl -X POST "http://127.0.0.1:8000/model/train" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC/USDT", "timeframe": "1h"}'

# 6. Сгенерировать сигнал
curl -X POST "http://127.0.0.1:8000/signal/latest" \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC/USDT", "timeframe": "15m", "auto_trade": false}'
```

---

## 📌 Дополнительная информация

- **Таймфреймы:** `1m`, `5m`, `15m`, `1h`, `4h`, `1d`
- **Биржи:** `bybit` (основная), `binance` (поддерживается через ccxt)
- **Логи:** `logs/app.log`, `logs/server.log`
- **Артефакты:** `artifacts/models/*.pkl`, `artifacts/reports/*.html`
- **Конфигурация:** `artifacts/config/*.json`

---

## 🔗 Ссылки

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — обзор архитектуры
- [ROADMAP.md](ROADMAP.md) — дорожная карта развития
- [NEXT_STEPS.md](NEXT_STEPS.md) — план задач
- [CHANGELOG.md](CHANGELOG.md) — история изменений

---

**Последнее обновление:** 2025-10-10  
**Версия API:** 0.8

