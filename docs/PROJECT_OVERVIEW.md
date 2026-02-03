# 🤖 MyAssistent — Обзор Проекта

## Краткое Описание

**MyAssistent** — автономный локальный торговый бот с машинным обучением для криптовалютной биржи Bybit. Система работает на Windows 10, обеспечивая полный цикл от сбора данных до генерации торговых сигналов с интеллектуальным риск-менеджментом.

### Ключевые Характеристики
- **Стартовый капитал:** 1000 ₽ (paper trading)
- **Биржа:** Bybit (spot, в планах — futures)
- **ML-движок:** XGBoost с автоматическим подбором порога
- **Управление:** FastAPI + Swagger UI + Streamlit Dashboard
- **Уведомления:** Telegram (сигналы, отчёты, аварии)
- **Режим работы:** Локально, пока включён ПК

## Технологический Стек

### Backend
- **FastAPI** — REST API, 80+ эндпоинтов, 12 теговых групп
- **SQLAlchemy 2.0** — ORM для работы с БД
- **SQLite** — база данных (`assistant.db`, в планах миграция на PostgreSQL)
- **APScheduler** — фоновые задачи (цены каждые 3 мин, модели ночью)
- **Pydantic v2** — валидация запросов и конфигурации

### ML & Data
- **XGBoost** — градиентный бустинг для прогнозов
- **scikit-learn** — метрики, валидация, препроцессинг
- **pandas** — обработка таймсерий
- **pandas-ta** — технические индикаторы (RSI, BB, EMA)
- **joblib** — сериализация моделей

### Market Data
- **ccxt** — унифицированный доступ к биржам (Binance, Bybit)
- **pybit** — нативный клиент Bybit v5 API
- **feedparser** — парсинг RSS новостей (Cointelegraph, CoinDesk, The Block)

### UI & Notifications
- **Streamlit** — интерактивный дашборд (временное решение)
- **Jinja2** — HTML-отчёты
- **requests** — Telegram Bot API

### Development
- **pytest** — юнит-тесты
- **ruff** — быстрый линтер (замена flake8/isort)
- **black** — форматтер кода
- **mypy** — статическая типизация

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│  Windows 10 → start_server.bat                          │
│   ├─ uvicorn :8000 (FastAPI backend)                    │
│   └─ streamlit :8501 (UI dashboard)                     │
└─────────────────────────────────────────────────────────┘
         ↓                           ↓
   Swagger UI (/docs)          Streamlit GUI
   + X-API-Key auth           (buttons, charts, tables)
```

### Структура Проекта

```
myAssistent/
├── src/                    # Исходный код
│   ├── main.py             # FastAPI app (4000+ строк, 83 эндпоинта)
│   ├── config.py           # Настройки (dotenv, paths)
│   ├── db.py               # SQLAlchemy ORM (12 моделей)
│   ├── prices.py           # REST API Binance/Bybit → OHLCV
│   ├── features.py         # Датасет (RSI, BB, новости, 40+ фич)
│   ├── modeling.py         # XGBoost train, threshold grid, walk-forward CV
│   ├── champion.py         # OOS-оценка, promote по Sharpe/AUC
│   ├── model_registry.py   # Реестр активных моделей per pair/TF
│   ├── model_policy.py     # SLA: max_age_days, retrain_if_auc_below
│   ├── news.py             # RSS → feedparser → SQLite
│   ├── news_url.py         # Канонизация URL (убирает utm_*)
│   ├── analysis.py         # Sentiment (лексиконы RU/EN), теги
│   ├── risk.py             # Фильтры (волатильность, EMA, объём)
│   ├── risk_schema.py      # Pydantic схемы валидации
│   ├── trade.py            # Paper trading (JSON state), auto-sizing
│   ├── notify.py           # Telegram API, форматирование
│   ├── watchlist.py        # CRUD + auto-discovery (ccxt)
│   ├── automation.py       # APScheduler jobs
│   ├── reports.py          # HTML-отчёты
│   ├── cmd_parser.py       # Парсинг /buy /sell /close команд
│   └── logging_setup.py    # Настройка логирования
│
├── artifacts/              # Артефакты (вне git)
│   ├── config/             # JSON-конфиги (policy, watchlist, notify)
│   ├── models/             # *.pkl (XGB + метрики + фичи + threshold)
│   ├── reports/            # HTML-отчёты
│   ├── state/              # paper_state.json, trade_guard.json
│   └── backups/            # snapshot_*.zip
│
├── logs/                   # Логи (вне git)
│   ├── app.log             # Основной лог приложения
│   └── server.log          # Лог uvicorn
│
├── tests/                  # Тесты
│   └── test_cmd_parser.py  # Парсинг торговых команд
│
├── docs/                   # Документация
│   ├── PROJECT_OVERVIEW.md # Этот файл
│   ├── ROADMAP.md          # Дорожная карта
│   └── CHANGELOG.md        # История изменений
│
├── start_server.bat        # Запуск backend + UI (Windows)
├── streamlit_app.py        # Streamlit UI
├── requirements.txt        # Зависимости Python
├── pytest.ini              # Конфигурация pytest
├── .gitignore              # Исключения для git
├── .env                    # Переменные окружения (НЕ в git!)
├── env.example.txt         # Шаблон .env
├── JOURNAL.md              # Журнал разработки
└── README.md               # Краткая справка
```

## База Данных (assistant.db)

### Таблицы

#### Новости и Аналитика
- **Message** — хранилище сообщений памяти
- **Article** — RSS-новости (url unique, source, title, published_at)
- **ArticleAnnotation** — 1:1 к Article (lang, sentiment, tags)

#### Рыночные Данные
- **Price** — OHLCV свечи (unique: exchange+symbol+timeframe+ts)

#### ML и Модели
- **ModelRun** — журнал обучений (метрики, model_path, features_json)
- **SignalEvent** — сигналы (unique: exchange+symbol+tf+bar_dt)
- **SignalOutcome** — исходы сигналов (entry/exit/ret_h/mdd)

#### Paper Trading
- **Portfolio** — общий кэш (deprecated, используется trade.py state)
- **PaperPosition** — позиции в симе (unique: exchange+symbol)
- **PaperOrder** — история ордеров
- **PaperTrade** — заполнения (fills)
- **EquityPoint** — история equity для графиков

## Жизненный Цикл Сигнала

```
1. Сбор данных
   POST /prices/fetch → OHLCV → БД

2. Формирование датасета
   POST /dataset/build → RSI, BB, новости → features

3. Обучение модели
   POST /model/train → XGBoost → artifacts/models/*.pkl

4. Champion/Challenger
   POST /model/champion/promote_if_better → OOS-оценка → promote

5. Генерация сигнала
   POST /signal/latest → load_model_for → predict → фильтры → БД + TG

6. Автоторговля (опционально)
   paper_open_buy_auto → sizing по волатильности → paper_state.json
```

## Безопасность и Риск-Контроль

### Trade Guard (Kill Switch)
- **Режимы:** `live` / `close_only` / `locked`
- **Файл:** `artifacts/state/trade_guard.json`
- **API:** `GET/POST /trade/guard`

### Риск-Политика (policy.json)
```json
{
  "min_prob_gap": 0.02,           // мин. запас вероятности
  "cooldown_minutes": 90,         // пауза между сигналами
  "block_if_dead_volatility": true,
  "max_open_positions": 0,        // 0 = без лимита
  "buy_fraction": 0.10,           // доля капитала (10%)
  "fee_bps": 8.0,                 // комиссия
  "slip_bps": 5.0,                // проскальзывание
  "volatility_thresholds": {...}, // dead/hot границы
  "monitor": {...},               // мониторинг позиций
   "news_radar": {...},            // детектор всплесков
   "ema_strategy": {               // настройки EMA-стратегии монитора
      "fast_period": 12,
      "slow_period": 26,
      "rsi_period": 14,
      "rsi_overbought": 70,
      "rsi_oversold": 30,
      "volume_threshold": 1.2,
      "atr_period": 14,
      "fast_period_simple": 9,
      "slow_period_simple": 21
   }
}
```

### API-авторизация
- **Метод:** `X-API-Key` header
- **Исключения:** `/`, `/ping`, HTML-панели
- **Ошибки:** 401 (missing), 403 (invalid), 503 (misconfigured)

## Автоматизация (APScheduler)

| Job | Интервал | Действие |
|-----|----------|----------|
| job_watchlist_discover | 6 часов | Добавляет топ-25 пар по объёму |
| job_prices_sync | 3 минуты | Загружает OHLCV для watchlist |
| job_news_fetch | 5 минут | Подтягивает RSS-ленты |
| job_news_analyze | 10 минут | Sentiment + tags разметка |
| job_models_maint | 03:20 UTC | Переобучение по SLA |
| job_signals_cycle | 5 минут | Сигналы + TG + auto-trade |
| job_daily_report | 03:50 UTC | HTML-отчёт + TG |

## Конфигурация

### Переменные Окружения (.env)
- `API_KEY` — ключ для X-API-Key auth
- `DATABASE_URL` — путь к БД (SQLite/PostgreSQL)
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — уведомления
- `TRADE_MODE` — режим торговли (live/close_only/locked)
- `BYBIT_API_KEY` / `BYBIT_API_SECRET` — для реальной торговли

### Файловые Конфиги (artifacts/config/)
- `policy.json` — риск-политика
- `model_policy.json` — SLA моделей
- `notify.json` — настройки уведомлений
- `watchlist.json` — список отслеживаемых пар
- `active_models.json` — ручной выбор моделей

## Запуск

```batch
# Windows (start_server.bat)
start_server.bat

# Альтернативно (вручную):
.venv\Scripts\activate
uvicorn src.main:app --host 127.0.0.1 --port 8000
streamlit run streamlit_app.py --server.port 8501
```

### Доступ
- **Backend API:** http://127.0.0.1:8000
- **Swagger UI:** http://127.0.0.1:8000/docs
- **Streamlit UI:** http://localhost:8501

## Мониторинг и Отладка

### Логи
- `logs/app.log` — основной лог (INFO/DEBUG/WARNING/ERROR)
- `logs/server.log` — uvicorn лог

### Диагностика
- `GET /_debug/info` — список роутов, cwd, sys.path
- `GET /_debug/env` — переменные окружения (masked)
- `GET /automation/status` — статус APScheduler jobs

### Метрики
- `artifacts/metrics.json` — метрики последней модели
- `GET /ui/summary` — сводка (equity, positions, signals)
- `GET /model/health` — свежесть моделей по watchlist

## Основные Эндпоинты

### Управление Данными
- `POST /news/fetch` — RSS загрузка
- `POST /prices/fetch` — OHLCV загрузка
- `POST /dataset/build` — формирование датасета

### ML и Модели
- `POST /model/train` — обучение XGBoost
- `POST /model/train_missing` — умная дотренировка по SLA
- `GET /model/health` — статус свежести моделей
- `POST /model/champion/promote_if_better` — champion/challenger

### Сигналы
- `POST /signal/latest` — inference + фильтры + DB + TG
- `GET /signals/recent` — последние события

### Торговля (Paper)
- `GET /trade/positions` — открытые позиции
- `GET /trade/equity` — cash + positions → equity
- `POST /trade/paper/close` — закрыть пару
- `POST /trade/manual/buy` — ручная покупка

### Автоматизация
- `GET /automation/status` — список jobs
- `POST /automation/run` — разовый запуск

## SLA Моделей (model_policy.json)

```json
{
  "max_age_days": 7,              // переобучать если > 7 дней
  "retrain_if_auc_below": 0.55,   // переобучать если AUC < 0.55
  "min_train_rows": 200,          // минимум строк для обучения
  "promote_if_auc_gain": 0.005    // промоутить если ΔAUC ≥ 0.5%
}
```

## Фичи (40+)

### Ценовые
- `ret_1`, `ret_3`, `ret_6`, `ret_12` — доходности
- `vol_norm` — нормализованный объём

### Технические
- `rsi_14` — RSI(14)
- `bb_pct_20_2`, `bb_width_20_2` — Bollinger Bands

### Новостные
- `news_cnt_6`, `news_cnt_24` — счётчики новостей
- `sent_mean_6`, `sent_mean_24` — средний sentiment
- `tag_<name>_6`, `tag_<name>_24` — частота тегов (btc, eth, etf, sec, hack, etc.)

### Целевая Переменная
- `future_ret` — доходность через `horizon_steps` баров
- `y` — бинарная метка (future_ret > 0)

## Ограничения и Известные Проблемы

1. **SQLite не подходит для конкурентных записей** — при миграции на продакшн → Postgres
2. **Отсутствие миграций БД** — изменения схемы требуют пересоздания БД (в планах: Alembic)
3. **main.py перегружен** — 4000+ строк, требуется декомпозиция на роутеры
4. **Низкий coverage тестов** — <5%, нужны тесты для modeling, features, trade
5. **Две базы данных** — assistant.db (52 MB) и app.db (8.9 MB) требуют объединения

## Дальнейшее Развитие

См. [ROADMAP.md](ROADMAP.md) для детального плана развития проекта.

## Контакты и Поддержка

Проект разрабатывается для личного использования. Вопросы и предложения — через GitHub Issues.

