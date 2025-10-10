# 🤖 MyAssistent — Автономный ML-Трейдер для Bybit

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-Private-red.svg)]()

Локальный торговый бот с машинным обучением для криптовалютной биржи Bybit. Полный цикл: от сбора данных до генерации торговых сигналов с интеллектуальным риск-менеджментом.

## ⚡ Быстрый Старт

### Требования
- **Windows 10/11**
- **Python 3.11+** (64-bit)
- **Git** (для клонирования репо)

### Установка

```bash
# 1. Клонировать репозиторий
git clone https://github.com/yourusername/myAssistent.git
cd myAssistent

# 2. Создать виртуальное окружение (автоматически при запуске start_server.bat)
# Или вручную:
python -m venv .venv
.venv\Scripts\activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить переменные окружения
# Скопировать env.example.txt в .env и заполнить:
# - API_KEY (генерировать: openssl rand -hex 32)
# - TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (для уведомлений)
```

### Запуск

```batch
# Автоматический запуск backend + UI
start_server.bat

# Альтернативно (вручную):
# Backend (FastAPI)
.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000

# UI (Streamlit) — в отдельном окне
.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.port 8501
```

### Доступ

- **Backend API:** http://127.0.0.1:8000
- **Swagger UI (документация):** http://127.0.0.1:8000/docs
- **Streamlit Dashboard:** http://localhost:8501

## 🎯 Основные Функции

### ✅ Реализовано

- **ML-Прогнозы:** XGBoost с автоподбором порога, walk-forward CV
- **Champion/Challenger:** Автоматический отбор лучших моделей
- **SLA Моделей:** Переобучение при max_age_days > 7 или ROC-AUC < 0.55
- **Paper Trading:** Симулятор с auto-sizing от equity
- **Риск-Менеджмент:** Фильтры (волатильность, EMA, объём), kill switch
- **Новости:** RSS (Cointelegraph, CoinDesk) + sentiment-анализ
- **Уведомления:** Telegram (сигналы, отчёты, алерты)
- **Автоматизация:** APScheduler (цены каждые 3 мин, модели ночью)
- **Динамический Watchlist:** Auto-discovery топ-пар по объёму

### 📊 Метрики

- **Стартовый капитал:** 1000 ₽ (paper trading)
- **Фичи:** 40+ (RSI, BB, EMA, новости, sentiment)
- **Эндпоинты:** 80+ (REST API)
- **Таблицы БД:** 12 (SQLite → планируется Postgres)
- **Тесты:** В разработке (target: >80% coverage)

## 📚 Документация

- **[PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)** — подробный обзор архитектуры
- **[ROADMAP.md](docs/ROADMAP.md)** — дорожная карта развития
- **[CHANGELOG.md](docs/CHANGELOG.md)** — история изменений
- **[JOURNAL.md](JOURNAL.md)** — журнал разработки

## 🛠️ Технологии

### Backend
- FastAPI, SQLAlchemy 2.0, SQLite
- XGBoost, scikit-learn, pandas
- APScheduler, Pydantic v2

### Market Data
- ccxt (Binance, Bybit), pybit
- feedparser (RSS новости)

### UI & Monitoring
- Streamlit, Jinja2 (HTML-отчёты)
- Telegram Bot API

### Development
- pytest, ruff, black, mypy
- alembic (миграции БД)

## 🚀 Использование

### Основные API Эндпоинты

#### Новости
```bash
# Подтянуть RSS-ленты
curl -X POST http://127.0.0.1:8000/news/fetch \
  -H "X-API-Key: YOUR_API_KEY"

# Проанализировать (sentiment + tags)
curl -X POST http://127.0.0.1:8000/news/analyze \
  -H "X-API-Key: YOUR_API_KEY"
```

#### Цены
```bash
# Загрузить OHLCV
curl -X POST http://127.0.0.1:8000/prices/fetch \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"exchange":"bybit", "symbol":"BTC/USDT", "timeframe":"15m", "limit":500}'
```

#### Модели
```bash
# Обучить модель
curl -X POST http://127.0.0.1:8000/model/train \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"exchange":"bybit", "symbol":"BTC/USDT", "timeframe":"15m", "horizon_steps":12}'

# Проверить здоровье моделей
curl http://127.0.0.1:8000/model/health?exchange=bybit \
  -H "X-API-Key: YOUR_API_KEY"
```

#### Сигналы
```bash
# Получить сигнал (inference + фильтры + DB + Telegram)
curl -X POST http://127.0.0.1:8000/signal/latest \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"exchange":"bybit", "symbol":"BTC/USDT", "timeframe":"15m", "horizon_steps":12}'
```

#### Торговля
```bash
# Открытые позиции
curl http://127.0.0.1:8000/trade/positions \
  -H "X-API-Key: YOUR_API_KEY"

# Equity (cash + positions)
curl http://127.0.0.1:8000/trade/equity \
  -H "X-API-Key: YOUR_API_KEY"
```

### Полная документация API: http://127.0.0.1:8000/docs

## ⚙️ Конфигурация

### Переменные Окружения (.env)

```bash
# API
API_KEY=your_api_key_here_generate_with_openssl_rand_hex_32
DATABASE_URL=sqlite:///./assistant.db

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trade Mode
TRADE_MODE=live  # live | close_only | locked

# Automation
PRICES_EVERY_MIN=3
MODELS_DAILY_UTC=03:20
```

### Конфигурационные Файлы

- `artifacts/config/policy.json` — риск-политика
- `artifacts/config/model_policy.json` — SLA моделей
- `artifacts/config/notify.json` — настройки уведомлений
- `artifacts/config/watchlist.json` — отслеживаемые пары
- `artifacts/config/active_models.json` — ручной выбор моделей

## 🧪 Тестирование

```bash
# Запустить тесты
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Только конкретный модуль
pytest tests/test_cmd_parser.py -v
```

## 🔒 Безопасность

### Trade Guard (Kill Switch)

```bash
# Проверить текущий режим
curl http://127.0.0.1:8000/trade/guard -H "X-API-Key: YOUR_API_KEY"

# Установить режим "только закрытие"
curl -X POST http://127.0.0.1:8000/trade/guard \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"close_only", "reason":"Market volatility too high"}'

# Заблокировать всё
curl -X POST http://127.0.0.1:8000/trade/guard \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"mode":"locked", "reason":"Emergency stop"}'
```

### Риск-Контроль

- **Cooldown:** 90 мин между сигналами на одну пару
- **Max Open Positions:** Лимит одновременных позиций
- **Position Max Fraction:** Макс. доля капитала в одной монете
- **Волатильность-фильтры:** Блокировка при dead/hot волатильности
- **Комиссии:** 8 bps, проскальзывание 5 bps (в симуляторе)

## 📈 Дорожная Карта

См. [ROADMAP.md](docs/ROADMAP.md)

### Ближайшие Версии

- **v0.8** — Рефакторинг (декомпозиция main.py, Alembic, тесты)
- **v0.9** — Postgres + MLflow + Next.js UI
- **v1.0** — FinBERT, расширенные фичи, бэктестинг
- **v1.1** — Reinforcement Learning
- **v1.2** — Real Trading (после успешного testnet)

## 🤝 Разработка

### Линтеры и Форматтеры

```bash
# Ruff (линтер)
ruff check src/ --fix

# Black (форматтер)
black src/

# Mypy (типы)
mypy src/ --ignore-missing-imports
```

### Миграции БД (Alembic)

```bash
# Инициализация (при первом запуске)
alembic init alembic

# Создать миграцию
alembic revision --autogenerate -m "description"

# Применить миграции
alembic upgrade head
```

### Структура Коммитов

Используем [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: добавлена поддержка Futures
fix: исправлена утечка памяти в features.py
docs: обновлён README
refactor: декомпозиция main.py на роутеры
test: добавлены тесты для modeling.py
```

## 📝 Лицензия

Проект разрабатывается для личного использования. Все права защищены.

## 🐛 Известные Проблемы

- SQLite не подходит для конкурентных записей → миграция на Postgres в v0.9
- main.py перегружен (4000+ строк) → декомпозиция в v0.8
- Низкий coverage тестов (<5%) → target >80% в v0.8
- Две БД (assistant.db + app.db) → объединены в v0.7

## 💬 Контакты

- **GitHub:** https://github.com/yourusername/myAssistent
- **Issues:** https://github.com/yourusername/myAssistent/issues

---

**⚠️ Disclaimer:** Данный софт предназначен исключительно для образовательных целей. Торговля криптовалютами сопряжена с высоким риском. Используйте на свой страх и риск. Автор не несёт ответственности за финансовые потери.

