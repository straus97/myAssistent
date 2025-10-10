# 📝 История Изменений

Все значимые изменения в этом проекте документируются в данном файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и версионирование следует [Semantic Versioning](https://semver.org/lang/ru/).

---

## [Unreleased]

---

## [0.8.0] — 2025-10-10

### Добавлено
- **Comprehensive тесты (127 тестов, 100% passed):**
  - `tests/test_modeling.py` — 20 тестов для ML-пайплайна (XGBoost, threshold grid, walk-forward CV)
  - `tests/test_features.py` — 30+ тестов для фичей (RSI, Bollinger Bands, новостные агрегаты, датасет)
  - `tests/test_trade.py` — 40+ тестов для paper trading (sizing, PnL, позиции, ордера)
  - `tests/test_risk.py` — 35+ тестов для риск-менеджмента (фильтры, EMA, волатильность, policy)
  - **Coverage:** modeling.py 96%, risk.py 96%, trade.py 87%, features.py 63%
  - **Результаты:** 127/127 тестов passed (100% success rate)

- **Документация API (`docs/API.md`):**
  - Comprehensive описание 80+ эндпоинтов
  - Примеры запросов/ответов для всех групп (News, Prices, Models, Signals, Trade, etc.)
  - Полный цикл использования с curl примерами
  - Документация авторизации, форматов ответов, таймфреймов

- **CI/CD Pipeline (`.github/workflows/ci.yml`):**
  - Lint & Format Check (ruff, black)
  - Type Check (mypy)
  - Tests & Coverage (pytest + codecov integration)
  - Security Scan (bandit)
  - Dependency Audit (pip-audit)
  - Автоматические артефакты и summary reports

### Исправлено
- **Все провалы в тестах (commit 632759f):**
  - Изолирован shared state в test_trade.py (улучшена fixture clean_state)
  - Исправлены моки БД в test_features.py (обработка multiple args в query)
  - Исправлен тест RSI с реалистичными данными
  - Исправлены assertions с float precision (допуск 1e-6)
  - Разделён виртуальный/реальный режим в _calc_auto_qty тестах

### Изменено
- **Push в GitHub (commits c56e7c2, 632759f):**
  - Версия 0.8 полностью завершена и отправлена в репозиторий
  - GitHub warning: assistant.db (51.94 MB) > рекомендуемого лимита (50 MB)

---

## [0.7.2] — 2025-10-10

- **Декомпозиция main.py на роутеры** (Часть 1/2, commit ce66572):
  - `src/dependencies.py` — общие зависимости (get_db, require_api_key, ok, err)
  - `src/utils.py` — утилиты (_now_utc, _atr_pct, _volatility_guard, _policy_vol_thr и др.)
  - `src/routers/` — 15 модульных роутеров по доменам:
    - ✅ `news.py` (7 эндпоинтов + News Radar) — полностью
    - ✅ `prices.py` (2 эндпоинта) — полностью
    - ✅ `dataset.py` (1 эндпоинт) — полностью
    - ✅ `report.py` (2 эндпоинта) — полностью
    - ✅ `watchlist.py` (6 эндпоинтов) — полностью
    - ✅ `risk.py` (2 эндпоинта) — полностью
    - ✅ `notify.py` (3 эндпоинта) — полностью
    - ✅ `models.py` (10 эндпоинтов) — полностью
    - ✅ `signals.py` (4 эндпоинта) — полностью
    - ⏳ `trade.py` (16 эндпоинтов) — основные работают, ручные команды - заглушки
    - ⏳ `automation.py` (2 эндпоинта) — заглушки (требуют scheduler instance)
    - ⏳ `ui.py` (3 эндпоинта) — заглушки (требуют HTML-генерации)
    - ⏳ `journal.py` (2 эндпоинта) — заглушки
    - ⏳ `backup.py` (1 эндпоинт) — заглушка
    - ✅ `db_admin.py` (3 эндпоинта) — основные работают
    - ✅ `debug.py` (3 эндпоинта) — работают
- **Pre-commit хуки** (`.pre-commit-config.yaml`):
  - Ruff (линтер с автоисправлением)
  - Black (форматтер, line-length=120)
  - Trailing whitespace, end-of-file-fixer
  - Check large files (>1MB), merge conflicts, YAML/JSON
  - Detect secrets (API keys, passwords)
  - Prettier для JSON/YAML/Markdown
- **Документация для следующих шагов:**
  - `docs/NEXT_STEPS.md` — детальный план задач для новых чатов
  - Задача #1: Декомпозиция main.py на роутеры (пошаговый план)
  - Задача #2: Расширение тестов (>80% coverage)
  - Задача #3: Исправление ruff ошибок
  - Задача #4: CI/CD pipeline (GitHub Actions)
  - Задача #5: Миграция на PostgreSQL
- `pre-commit>=3.6.0` в requirements.txt
- `.secrets.baseline` для detect-secrets

### Изменено
- Обновлена память о структуре проекта (версия 0.7 → 0.8)
- Обновлён `docs/NEXT_STEPS.md` с прогрессом декомпозиции

### Изменено (2025-10-10, commit 9484232)
- **Декомпозиция main.py завершена (Часть 2/2)**:
  - main.py сокращён с 4716 строк до 780 строк (~84% reduction)
  - Подключены все 15 роутеров через `app.include_router()`
  - Удалены дублирующиеся функции:
    - `ok()`, `err()`, `require_api_key()` → перенесены в `src/dependencies.py`
    - `_now_utc()`, `_atr_pct()`, `_volatility_guard()` и др. → перенесены в `src/utils.py`
  - Оставлены только:
    - Создание FastAPI app
    - CORS middleware
    - Artifacts static files
    - APScheduler с 12 job функциями
    - Startup/shutdown events (scheduler lock, indexes, cleanup)
    - Корневые эндпоинты (/, /ping, /hello, /time, /memory/*)
  - Создан бэкап: `src/main_old.py` (4716 lines)
  - Исправлена ошибка импорта `Field` из pydantic в signals.py

### Добавлено (2025-10-10, commits 8240b7c, 1e394b0, 4c96056)
- **Завершены все роутеры (15/15):**
  - automation.py: scheduler status + manual job execution (fetch_news, make_signals, etc.)
  - ui.py: HTML summary + equity chart (встроенный JS/CSS)
  - journal.py: CSV/XLSX export with XlsxWriter formatting
  - backup.py: ZIP snapshot creation (БД + config + models)
  - trade.py: manual commands (buy/sell/short/cover) с полной реализацией PnL tracking

- **Исправлены ruff ошибки:**
  - Было: 23 ошибки (E701, E702, E722, E741, E711, F401, F541, F841)
  - Стало: 3 ошибки (все в main_old.py - бэкап файл)
  - Все активные файлы: ✅ ruff-compliant

**Итого:**
- ✅ 15 роутеров полностью работают
- ✅ 80+ эндпоинтов
- ✅ main.py: 4716 → 780 строк (~84% reduction)
- ✅ Код проверен линтером (ruff)
- ✅ Импорты работают

### В работе (Часть 3/3)
- Тестирование всех эндпоинтов в Swagger UI (частично)
- Расширение тестов (coverage >80%) - для версии 0.8.1

---

## [0.7.1] — 2025-10-10

### Добавлено
- Документация проекта:
  - `docs/PROJECT_OVERVIEW.md` — подробный обзор архитектуры
  - `docs/ROADMAP.md` — дорожная карта развития
  - `docs/CHANGELOG.md` — этот файл
- `env.example.txt` — шаблон переменных окружения
- Расширенный `requirements.txt` с секциями и dev-зависимостями:
  - `ruff>=0.1.9` — быстрый линтер
  - `black>=23.12.0` — форматтер кода
  - `mypy>=1.8.0` — статическая типизация
  - `pytest>=7.4`, `pytest-cov>=4.1` — тестирование
  - `alembic>=1.12` — миграции БД
  - `joblib>=1.3` — сериализация моделей
  - `pybit>=5.6` — нативный клиент Bybit v5

### Изменено
- Объединены базы данных: используется только `assistant.db` (было: `assistant.db` + `app.db`)
- Обновлён `src/config.py`: комментарий о unified database
- Обновлён `start_server.bat`: `DATABASE_URL=sqlite:///./assistant.db`
- Структурированы зависимости в `requirements.txt` (группировка по назначению)

### Удалено
- `src/hello_ai.py` — устаревший утилита для env-лога

---

## [0.7.0] — 2025-10-10

### Добавлено
- **SLA моделей** (`src/model_policy.py`):
  - Автоматическое переобучение при max_age_days > 7
  - Переобучение при ROC-AUC < 0.55
  - Политика промоута: promote_if_auc_gain ≥ 0.005
- **Champion/Challenger отбор** (`src/champion.py`):
  - OOS-оценка на роллинговом хвосте (tail_rows=1800)
  - Автоматический промоут при превосходстве по Sharpe/AUC
  - Telegram-уведомления о промоуте (🏆 PROMOTE)
- **Реестр активных моделей** (`src/model_registry.py`):
  - Ручной выбор модели per pair/TF/horizon (`active_models.json`)
  - Автовыбор: приоритет ручной → последний прогон → fallback
  - Эндпоинты: `GET/POST /model/active`
- **Динамический watchlist** (`src/watchlist.py`):
  - CRUD эндпоинты: `GET/POST /watchlist`, `/watchlist/add`, `/watchlist/remove`
  - Auto-discovery топ-ликвидных пар через ccxt
  - Эндпоинт: `POST /watchlist/discover`
- **News Radar** — детектор всплесков новостей:
  - Анализ частоты новостей в скользящем окне
  - Фильтрация по unique sources, sentiment, тегам
  - Cooldown для предотвращения спама
- **Monitor** — мониторинг открытых позиций:
  - Partial close при прибыли > partial_at (по умолчанию +3%)
  - Flat close при убытке < flat_after (по умолчанию -1%)
  - Настройки в `policy.json.monitor`
- **Trade Guard (Kill Switch)**:
  - Режимы: `live`, `close_only`, `locked`
  - Эндпоинты: `GET/POST /trade/guard`
  - Файл: `artifacts/state/trade_guard.json`
- **Pydantic валидация конфигурации** (`src/risk_schema.py`):
  - Строгие схемы для Policy, Monitor, NewsRadar, VolThresh
  - Валидация bounds (dead < hot, partial_at > 0, etc.)
  - Человекочитаемые ошибки через `explain_validation_errors()`

### Изменено
- **Обновлён ML-пайплайн**:
  - Walk-forward CV с подбором порога на inner_valid
  - Equity curve усечённая до 400 точек (для metrics.json)
  - Метрики: accuracy, roc_auc, total_return, sharpe_like
- **Автоматизация (APScheduler)**:
  - job_watchlist_discover — каждые 6 часов
  - job_models_maint — ночью в 03:20 UTC (с учётом SLA)
  - job_signals_cycle — каждые 5 минут (с фильтрами и auto-trade)
- **Улучшены фильтры сигналов** (`src/risk.py`):
  - Волатильность-классификация (dead/normal/hot)
  - Фильтры: min_rel_volume, max_bar_change, require_uptrend
  - Метрики фильтров сохраняются в SignalEvent.note
- **Paper trading** (`src/trade.py`):
  - Auto-sizing от реального equity с учётом волатильности
  - Лимиты: max_open_positions, position_max_fraction
  - Atomic writes через NamedTemporaryFile
- **Telegram уведомления** (`src/notify.py`):
  - Новый «человеческий» формат сообщений
  - Стили: `simple` (по умолчанию) и `raw` (отладочный)
  - Быстрая команда для SELL в сообщении
  - Волатильность-эмодзи: 🔥 hot, 🧊 dead, 〰️ normal
- **Канонизация URL** (`src/news_url.py`):
  - Убирает utm_*, fbclid, gclid и др. трекеры
  - Нормализует хост (убирает www), path, query
  - Дедупликация новостей по каноническому URL

### Исправлено
- **Дедупликация новостей** (`src/news.py`):
  - Жёсткая дедупликация по каноническому URL
  - Мягкая дедупликация по source + title в окне ±48h
  - Корректный парсинг published_at (feedparser + dateutil)
- **Фичи** (`src/features.py`):
  - RSI(14) по Уайлдеру через EWM (alpha=1/14)
  - Bollinger Bands с ddof=0, min_periods=window
  - Клиппинг bb_width (без inf/-inf)
- **Модели** (`src/modeling.py`):
  - Безопасный сабсет фичей (только существующие колонки)
  - Логирование missing features
  - Единый формат .pkl (было: .pkl и .joblib)

### Безопасность
- Добавлена валидация всех входных параметров через Pydantic
- Kill switch для экстренной остановки торговли
- Лимиты позиций для защиты от переторговли
- Комиссии и проскальзывание учитываются в симуляторе

---

## [0.6.0] — 2025-10-07

### Добавлено
- **Sentiment-анализ новостей** (`src/analysis.py`):
  - Лексиконный подход (POS/NEG словари для RU/EN)
  - Автотеггинг: btc, eth, etf, sec, hack, regulation, listing, adoption, bullish, bearish, halving
  - Определение языка (эвристика по доле кириллицы/латиницы)
- **Интеграция новостей в фичи** (`src/features.py`):
  - Агрегация новостей по таймфрейму свечи
  - Роллинговые окна: news_cnt_6/24, sent_mean_6/24, tag_*_6/24
  - Всего: 11 тегов × 2 окна = 22 новостных фичи
- **XGBoost обучение** (`src/modeling.py`):
  - Threshold grid search [0.50..0.70] по Sharpe → total_return → AUC
  - Сохранение метрик в `artifacts/metrics.json` и `artifacts/features.json`
  - Регистрация обучений в таблице `ModelRun`
- **Сигналы и события** (`src/main.py`):
  - Таблица `SignalEvent` (unique: exchange+symbol+tf+bar_dt)
  - Эндпоинты: `POST /signal/latest`, `GET /signals/recent`
  - Автоматическая генерация сигналов каждые 15 минут (планировщик)

### Изменено
- **Датасет** (`src/features.py`):
  - Добавлены технические индикаторы: RSI(14), BB(20,2)
  - Расширены ценовые фичи: ret_1/3/6/12, vol_norm
  - Целевая переменная: future_ret, y (бинарная)

### Исправлено
- Корректная обработка NaN/inf в фичах (dropna, clip)
- Убраны устаревшие vaderSentiment, langdetect (заменены на лексиконы)

---

## [0.5.0] — 2025-10-05

### Добавлено
- **RSS новости** (`src/news.py`):
  - Интеграция feedparser для загрузки RSS
  - Таблицы: Article, ArticleAnnotation
  - Эндпоинты: `POST /news/fetch`, `GET /news/latest`, `GET /news/search`
- **OHLCV загрузка** (`src/prices.py`):
  - Поддержка Binance и Bybit через REST API
  - Таблица Price (unique: exchange+symbol+timeframe+ts)
  - Эндпоинты: `POST /prices/fetch`, `GET /prices/latest`
- **APScheduler**:
  - Фоновые задачи: сбор новостей (5 мин), цен (15 мин), ежедневный отчёт (00:50 UTC)
  - Эндпоинт: `GET /automation/status`

### Изменено
- **SQLAlchemy 2.0**:
  - Обновлены модели с UniqueConstraint и Index
  - Добавлены helper-функции: ensure_runtime_indexes()

---

## [0.4.0] — 2025-09-30

### Добавлено
- **FastAPI базовое приложение** (`src/main.py`):
  - Роуты: `/hello`, `/time`, `/ping`, `/_debug/info`
  - Swagger UI на `/docs`
  - Offline-доки через fastapi_offline (опционально)
- **SQLAlchemy ORM** (`src/db.py`):
  - Модели: Message, Article, Price
  - SQLite по умолчанию (`assistant.db`)
- **Streamlit UI** (`streamlit_app.py`):
  - Кнопки управления (загрузка новостей, цен, обучение)
  - График цены (line chart)
  - Таблицы новостей и обучений

### Инфраструктура
- Виртуальное окружение: `.venv`
- Батник запуска: `start_server.bat` (backend + UI)
- Логирование: `logs/app.log`, `logs/server.log`

---

## [0.3.0] — 2025-09-28

### Добавлено
- **Git репозиторий**:
  - Настройки: user.name, user.email, init.defaultBranch=main
  - Первый коммит с базовой структурой
- **Конфигурация** (`src/config.py`):
  - Настройки через dotenv (`.env`)
  - Переменные: DATABASE_URL, LOG_DIR, ARTIFACTS_DIR, TELEGRAM_BOT_TOKEN, etc.

---

## [0.2.0] — 2025-09-25

### Добавлено
- **Базовая структура проекта**:
  - Директории: `src/`, `logs/`, `artifacts/`, `tests/`
  - Файлы: `requirements.txt`, `.gitignore`, `README.md`, `JOURNAL.md`
- **Python окружение**:
  - Python 3.11 (x64)
  - Виртуальное окружение `.venv`
  - Базовые пакеты: fastapi, uvicorn, pydantic, sqlalchemy, pandas, numpy

---

## [0.1.0] — 2025-09-20

### Добавлено
- **Инициализация проекта**:
  - Создан каталог `C:\AI\myAssistent`
  - Установлен Git for Windows
  - Настроена IDE (PyCharm/VS Code)

---

## Формат Changelog

### Типы изменений
- **Добавлено** (Added) — новые функции
- **Изменено** (Changed) — изменения в существующей функциональности
- **Устарело** (Deprecated) — функции, которые скоро будут удалены
- **Удалено** (Removed) — удалённые функции
- **Исправлено** (Fixed) — исправления багов
- **Безопасность** (Security) — уязвимости и их исправления

### Ссылки на версии
- [Unreleased]: https://github.com/yourusername/myAssistent/compare/v0.7.0...HEAD
- [0.7.0]: https://github.com/yourusername/myAssistent/compare/v0.6.0...v0.7.0
- [0.6.0]: https://github.com/yourusername/myAssistent/compare/v0.5.0...v0.6.0
- [0.5.0]: https://github.com/yourusername/myAssistent/compare/v0.4.0...v0.5.0
- [0.4.0]: https://github.com/yourusername/myAssistent/compare/v0.3.0...v0.4.0
- [0.3.0]: https://github.com/yourusername/myAssistent/compare/v0.2.0...v0.3.0
- [0.2.0]: https://github.com/yourusername/myAssistent/compare/v0.1.0...v0.2.0
- [0.1.0]: https://github.com/yourusername/myAssistent/releases/tag/v0.1.0

