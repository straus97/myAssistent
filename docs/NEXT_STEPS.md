# 📋 Следующие Шаги — План Задач для Новых Чатов

> **Важно:** Каждая крупная задача требует отдельного чата. Перед началом нового чата читай этот файл + PROJECT_OVERVIEW.md + ROADMAP.md.

## Текущий Статус: Версия 0.7 → 0.8

**Завершено в предыдущем чате:**
- ✅ Объединена БД (assistant.db only)
- ✅ Добавлена документация (PROJECT_OVERVIEW, ROADMAP, CHANGELOG)
- ✅ Обновлён requirements.txt (ruff, black, mypy, pytest, alembic, pre-commit)
- ✅ Инициализированы Alembic миграции
- ✅ Создан .gitignore
- ✅ Создан .pre-commit-config.yaml
- ✅ Удалён src/hello_ai.py
- ✅ Обновлён README.md
- ✅ Применён Black форматтер
- ✅ Код закоммичен и отправлен в GitHub

**Завершено в текущем чате (2025-10-10):**
- ✅ Декомпозиция main.py на роутеры (Часть 1/2):
  - ✅ Создана структура src/routers/ с 15 роутерами
  - ✅ Создан src/dependencies.py (общие зависимости)
  - ✅ Создан src/utils.py (утилиты)
  - ✅ Полностью реализовано: news, prices, dataset, report, watchlist, risk, notify, models, signals
  - ⏳ Частично: trade (основные эндпоинты работают, ручные команды - заглушки)
  - ⏳ Заглушки: automation, ui, journal, backup

- ✅ Декомпозиция main.py (Часть 2/2 - завершено):
  - ✅ main.py сокращён с 4716 строк до 780 строк (~84% сокращение)
  - ✅ Подключены все 15 роутеров через app.include_router()
  - ✅ Удалены дублирующиеся функции (перенесены в dependencies.py и utils.py)
  - ✅ Оставлены только: app setup, CORS, static files, scheduler, startup/shutdown
  - ✅ Создан бэкап: src/main_old.py
  - ✅ Коммит: refactor: decompose main.py into modular routers (Part 2/2)

**Завершено дополнительно (2025-10-10):**
- ✅ Завершение заглушек в роутерах:
  - ✅ automation.py (scheduler status + manual job execution)
  - ✅ ui.py (HTML summary + equity chart)
  - ✅ journal.py (CSV/XLSX export)
  - ✅ backup.py (ZIP snapshot)
  - ✅ trade.py (manual buy/sell/short/cover commands)
- ✅ Исправление ruff ошибок (23 → 3, все активные файлы чистые)
- ✅ Все 15 роутеров полностью функциональны (80+ эндпоинтов)

**Завершено в версии 0.8 (2025-10-10):**
- ✅ Расширение тестов (127 тестов, **100% passed**)
  - ✅ tests/test_modeling.py (20 тестов: XGBoost, threshold grid, walk-forward CV) - 96% coverage
  - ✅ tests/test_features.py (30+ тестов: RSI, BB, новостные фичи, датасет) - 63% coverage
  - ✅ tests/test_trade.py (40+ тестов: paper trading, auto-sizing, PnL) - 87% coverage
  - ✅ tests/test_risk.py (35+ тестов: фильтры, волатильность, guard) - 96% coverage
- ✅ Создание docs/API.md (документация 80+ эндпоинтов с примерами)
- ✅ Настройка CI/CD (.github/workflows/ci.yml: lint, format, type-check, test, security)
- ✅ Исправление всех провалов в тестах (shared state, моки БД, float precision)
- ✅ Push в GitHub (commits: c56e7c2, 632759f)

**Версия 0.8 ЗАВЕРШЕНА! 🎉**

**Завершено дополнительно (2025-10-10 — версия 0.9):**
- ✅ assistant.db удалён из git tracking (commit 298b679)
- ✅ Создан docker-compose.yml для PostgreSQL 16 + pgbouncer
- ✅ Обновлён src/config.py и src/db.py для поддержки PostgreSQL
- ✅ Создана Alembic миграция для PostgreSQL индексов
- ✅ Создан скрипт миграции данных: scripts/migrate_sqlite_to_postgres.py
- ✅ Документация для новичков: docs/BEGINNER_GUIDE.md
- ✅ Чеклист готовности к продакшну: docs/PRODUCTION_READINESS.md
- ✅ Руководство по миграции: docs/POSTGRESQL_MIGRATION.md

**Осталось (опционально):**
- ⏳ Тестирование миграции на PostgreSQL (ручная проверка)
- ⏳ MLflow Tracking integration (Docker работает, нужна интеграция в src/modeling.py)
- ⏳ Next.js + TypeScript UI (структура готова, нужна разработка компонентов)
- ⏳ Prometheus + Grafana мониторинг (Docker работает, метрики экспортируются)

**Завершено (2025-10-10 — вечер):**
- ✅ Исправлена инфраструктура запуска:
  - ✅ Добавлен ENABLE_METRICS=true в start_server.bat
  - ✅ Создан start_all.bat для запуска полного стека
  - ✅ Создан frontend/.env.example для настройки Next.js
  - ✅ Обновлена docs/QUICK_START.md с подробными инструкциями
  - ✅ Обновлена docs/ROADMAP.md с новыми задачами (FinBERT, расширенные фичи, бэктестинг, RL)
- ✅ Теперь работают:
  - ✅ http://localhost:8000/metrics (Prometheus metrics)
  - ✅ http://localhost:5000 (MLflow UI через Docker)
  - ✅ http://localhost:9090 (Prometheus через Docker)
  - ✅ http://localhost:3001 (Grafana через Docker)
  - ✅ http://localhost:3000 (Next.js Frontend — при запуске через start_all.bat)

**Завершено (2025-10-10 — ночь):**
- ✅ **FinBERT sentiment-анализ:**
  - ✅ Интеграция ProsusAI/finbert модели (Transformers + PyTorch)
  - ✅ Функции sentiment_finbert() и sentiment_finbert_batch()
  - ✅ Точность: 100% vs 80% лексиконов (тест на 5 новостях)
  - ✅ Производительность: 0.02-0.03 сек после загрузки модели
  - ✅ Параметр use_finbert в POST /news/analyze
  - ✅ Git commit: 2be4903
  
- ✅ **Расширенные фичи (40+ → 78 фич):**
  - ✅ Технические индикаторы (+18): MACD, ADX, ATR, Stochastic, Williams %R, CCI, EMA crossovers
  - ✅ On-chain метрики (+9): src/onchain.py - Glassnode API (exchange flows, SOPR, MVRV, NUPL, Puell Multiple)
  - ✅ Macro данные (+7): src/macro.py - Fear & Greed Index (работает!), FRED API структура
  - ✅ Social signals (+5): src/social.py - Twitter, Reddit, Google Trends структура
  - ✅ **Протестировано:** Датасет успешно построен (724 строки × 71 фича)
  - ✅ Git commit: 18b9959
  
- ✅ **Улучшенные Telegram уведомления:**
  - ✅ Подробная информация (биржа, пара, цена, сигнал, волатильность, риски)
  - ✅ Рекомендации по размеру позиции
  - ✅ Быстрые команды (/buy, /sell)
  - ✅ Информация о модели
  - ✅ Git commit: 5295651
  
- ✅ **Исправления:**
  - ✅ POST /risk/policy - убрана обёртка "updates", работает в Swagger

**Завершено (2025-10-11 18:00):**
- ✅ **Docker Desktop настройка и документация:**
  - ✅ Создан docs/DOCKER_GUIDE.md (подробное руководство, 400+ строк)
  - ✅ Создан ЗАПУСК_СИСТЕМЫ.md (быстрый старт с инструкциями)
  - ✅ Создан .env файл с корректной конфигурацией
  - ✅ Создан frontend/.env.local для Next.js
  - ✅ Проверена готовность: Docker 28.5.1 ✅, Node.js v22.11.0 ✅, Python 3.11 ✅
  - ✅ Система готова к запуску через start_all.bat
  - ✅ Инструкции по работе с Docker Desktop (интерфейс, команды, устранение проблем)
  - ✅ Пошаговый план: загрузка данных → обучение → бэктест → RL-агент

**Завершено (2025-10-11 13:30):**
- ✅ **Векторизованный бэктестинг (ПРОТЕСТИРОВАНО):**
  - ✅ src/backtest.py - ядро бэктестинга (векторизация через pandas)
  - ✅ src/routers/backtest.py - API endpoints (POST /backtest/run, GET /backtest/results, GET /backtest/list, GET /backtest/compare, DELETE)
  - ✅ Реалистичная симуляция: комиссии (8 bps), проскальзывание (5 bps), latency (1-2 бара)
  - ✅ Метрики: Sharpe, Sortino, Calmar, Max DD, Win Rate, Avg Win/Loss, Profit Factor, Exposure Time
  - ✅ Сравнение с buy-and-hold бенчмарком (outperformance, beats_benchmark)
  - ✅ Детальный анализ просадок (величина, duration, recovery time)
  - ✅ Список сделок с деталями (entry/exit time, price, PnL, duration)
  - ✅ Сохранение результатов в artifacts/backtest/
  - ✅ **Исправлены баги:**
    - ✅ NaN в first row equity curve (3611beb)
    - ✅ Feature shape mismatch (71a9cd2)
    - ✅ Negative duration_bars для последней сделки (a5e5ff9)
  - ✅ **Тестирование на реальных данных:**
    - ✅ BTC/USDT 1h (2025-09-01 → 2025-10-10)
    - ✅ Total Return: +7.9% (vs Benchmark: +3.3%)
    - ✅ Sharpe: 0.91, Win Rate: 76.7%, Profit Factor: 5.91
    - ✅ Max DD: -7.1%, Outperformance: +139%
  - ✅ Git commits: c99a93b, 71a9cd2, 3611beb, a5e5ff9

**Завершено (2025-10-11 15:00):**
- ✅ **RL-агент (PPO) для динамического sizing (ЗАВЕРШЕНО):**
  - ✅ src/rl_env.py - Custom Gym environment для торговли
    - ✅ State space: equity + positions + 71 features + risk metrics
    - ✅ Action space: direction (hold/buy/sell) + sizing (1-20%)
    - ✅ Reward: Rolling Sharpe ratio (30-day window)
  - ✅ src/rl_agent.py - PPO agent (Stable-Baselines3)
    - ✅ Training: 50K timesteps, learning_rate=3e-4
    - ✅ Inference: deterministic predictions
    - ✅ Model saving: artifacts/rl_models/
  - ✅ src/routers/rl.py - API endpoints
    - ✅ POST /rl/train - обучение агента
    - ✅ POST /rl/predict - inference с моделью
    - ✅ POST /rl/performance - оценка производительности
    - ✅ GET /rl/models - список обученных моделей
  - ✅ Updated src/features.py - добавлена build_dataset_for_rl()
  - ✅ Updated src/prices.py - добавлена fetch_ohlcv()
  - ✅ **Тестирование на BTC/USDT 1h (3 месяца):**
    - ✅ Total Return: -0.77%
    - ✅ Sharpe: -1.13
    - ✅ Win Rate: 25%
    - ✅ Total Trades: 4
  - ✅ **Сравнение с XGBoost:**
    - ✅ XGBoost: +14.96% return, 1.12 Sharpe, 77.53% win rate
    - ✅ RL требует больше обучения (500K-1M timesteps)
    - ✅ Рекомендована гибридная модель (XGBoost direction + RL sizing)
  - ✅ Git commit: 801f814

---

---

## 🎯 ЗАДАЧИ ДЛЯ СЛЕДУЮЩЕГО ЧАТА (ПРИОРИТЕТ: ВЫСОКИЙ)

### ✅ Задача #1: Векторизованный Бэктестинг (ЗАВЕРШЕНО 2025-10-11)

**Статус:** ✅ ВЫПОЛНЕНО (2025-10-10 23:30, commit c99a93b)

**Цель:** Реалистичная симуляция стратегии на исторических данных.

**Файлы для создания:**
- `src/backtest.py` - основной модуль бэктестинга
- `src/routers/backtest.py` - API endpoints

**Функционал:**
1. Векторизованный бэктест через pandas (быстро)
2. Реалистичная симуляция:
   - Комиссии (8 bps по умолчанию)
   - Проскальзывание (5 bps)
   - Latency (задержка исполнения 1-2 бара)
3. Метрики:
   - Sharpe Ratio (risk-adjusted returns)
   - Sortino Ratio (downside deviation)
   - Calmar Ratio (return/max drawdown)
   - Max Drawdown (величина + duration + recovery time)
   - Win Rate, Avg Win/Loss
   - Total trades, Exposure time
4. Сравнение с бенчмарками:
   - Buy-and-hold (BTC/ETH)
   - 60/40 портфель
5. Визуализация:
   - Equity curve
   - Drawdown chart
   - Monthly returns heatmap

**API Endpoints:**
- `POST /backtest/run` - запуск бэктеста
- `GET /backtest/results/{run_id}` - получить результаты
- `GET /backtest/compare` - сравнить стратегии

**Пример использования:**
```python
POST /backtest/run
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "initial_capital": 1000,
  "model_path": "artifacts/models/model_latest.pkl"
}
```

**Критерии успеха:**
- Sharpe > 1.5 (хорошая стратегия)
- Max DD < 20% (контролируемый риск)
- Win Rate > 55%
- Outperforms buy-and-hold

---

### ✅ Задача #2: RL-агент для динамического sizing (ЗАВЕРШЕНО 2025-10-11)

**Статус:** ✅ ВЫПОЛНЕНО (2025-10-11 15:00, commit 801f814)

**Цель:** Reinforcement Learning для оптимального sizing позиций.

**Файлы для создания:**
- `src/rl_env.py` - Gym environment
- `src/rl_agent.py` - PPO agent (Stable-Baselines3)
- `src/routers/rl.py` - API endpoints

**Архитектура:**
1. Custom Gym Environment:
   - State space: [equity, positions, 78 features, risk metrics]
   - Action space: [buy/sell/hold, sizing 0.0-1.0]
   - Reward: Sharpe ratio (rolling window)
2. PPO Agent (Stable-Baselines3):
   - Policy: MlpPolicy
   - Learning rate: 3e-4
   - Training: Walk-forward (30-дневные окна)
3. Hybrid модель:
   - XGBoost → направление (buy/sell probability)
   - RL Agent → sizing (0.01-0.20 от капитала)

**Зависимости:**
```
stable-baselines3>=2.0
gymnasium>=0.28
tensorboard>=2.14
```

**API Endpoints:**
- `POST /rl/train` - обучение агента
- `POST /rl/predict` - предсказание sizing
- `GET /rl/performance` - метрики агента

**Критерии успеха:**
- RL > XGBoost (по Sharpe)
- Адаптация к волатильности (меньше sizing при высокой vol)
- Stable convergence (reward не прыгает)

---

### 📈 Задача #3: Обучить модель на 78 фичах

**Цель:** Проверить улучшение качества с новыми фичами.

**Шаги:**
1. Построить датасет (уже работает!)
2. Обучить XGBoost:
   ```
   POST /model/train
   {
     "exchange": "bybit",
     "symbol": "BTC/USDT",
     "timeframe": "1h"
   }
   ```
3. Сравнить метрики:
   - Старая модель (40 фич): AUC, Sharpe
   - Новая модель (78 фич): AUC, Sharpe
4. Feature importance анализ:
   - Топ-20 фич
   - Категории (технические vs новости vs on-chain)

**Ожидаемые улучшения:**
- AUC: 0.55-0.60 → 0.62-0.68 (+10-15%)
- Sharpe: 0.8-1.2 → 1.5-2.0 (+50-100%)

---

### 🔧 Задача #4: MLflow Integration

**Цель:** Логирование экспериментов и версионирование моделей.

**Интеграция в src/modeling.py:**
1. mlflow.start_run() при обучении
2. Логирование:
   - Параметры: exchange, symbol, TF, features
   - Метрики: accuracy, AUC, precision, recall
   - Артефакты: model.pkl, features.json, confusion_matrix.png
3. Model Registry:
   - Production, Staging, Archived

**UI:** http://localhost:5000 (уже работает через Docker)

---

## 🎯 Новые Задачи для Следующего Чата (СТАРЫЕ - ВЫПОЛНЕНЫ)

### Задача #1: FinBERT Sentiment-анализ (Приоритет: ВЫСОКИЙ)

**Цель:** Заменить/дополнить лексиконный sentiment-анализ моделью FinBERT.

#### Контекст
- **Текущий подход:** Лексиконы (RU/EN словари)
- **Проблема:** Низкая точность, не учитывает контекст
- **Решение:** Hugging Face Transformers + FinBERT

#### План Действий

1. **Установка зависимостей:**
```bash
pip install transformers>=4.30 torch>=2.0
```

2. **Интеграция в src/analysis.py:**
- Добавить функцию `sentiment_finbert(text: str) -> dict`
- Модели: `ProsusAI/finbert` или `yiyanghkust/finbert-tone`
- Вернуть: `{"label": "positive/negative/neutral", "score": 0.95}`

3. **Обновление БД:**
- Добавить колонки в `ArticleAnnotation`:
  - `sentiment_finbert` (float -1..1)
  - `sentiment_finbert_label` (str)
  - `sentiment_method` (str: "lexicon"/"finbert"/"ensemble")

4. **Сравнительное тестирование:**
- Запустить на последних 100 новостях
- Сравнить с лексиконным подходом
- Выбрать лучший или ensemble

5. **Оптимизация:**
- Batch inference (группы по 8-16)
- Кеширование результатов (избегать повторного анализа)
- CPU fallback (если нет GPU)

**Коммит:**
```bash
git add src/analysis.py src/db.py requirements.txt
git commit -m "feat: add FinBERT sentiment analysis

- Integrated ProsusAI/finbert model via Transformers
- Added sentiment_finbert() function with batch inference
- Updated ArticleAnnotation with finbert_* columns
- Comparative testing: FinBERT vs lexicon approach
- CPU/GPU support with automatic fallback"
```

---

### Задача #2: Расширенные Фичи (40+ → 100+) (Приоритет: ВЫСОКИЙ)

**Цель:** Добавить on-chain, макро и social фичи для улучшения моделей.

#### План

1. **On-chain метрики (Glassnode API):**
- Регистрация: https://glassnode.com/
- API key → .env
- Эндпоинты:
  - Exchange net flows
  - Active addresses
  - SOPR, MVRV
- Создать `src/onchain.py`

2. **Макроэкономика:**
- Federal Reserve Economic Data (FRED) API
- DXY, CPI, Treasury yields
- Создать `src/macro.py`

3. **Social signals:**
- Twitter API v2 (mentions, sentiment)
- Reddit API (r/cryptocurrency)
- Fear & Greed Index
- Создать `src/social.py`

4. **Технические индикаторы:**
- MACD, ADX, ATR (через pandas-ta)
- Обновить `src/features.py`

**Коммит:**
```bash
git commit -m "feat: add 60+ new features (on-chain, macro, social)

- Glassnode API integration (exchange flows, SOPR, MVRV)
- FRED API for macro data (CPI, DXY, yields)
- Twitter/Reddit sentiment aggregation
- Extended technical indicators (MACD, ADX, ATR)
- Total features: 40 → 103"
```

---

### Задача #3: Векторизованный Бэктестинг (Приоритет: СРЕДНИЙ)

**Цель:** Реалистичная симуляция стратегии на исторических данных.

#### План

1. **Создать src/backtest.py:**
```python
def run_backtest(
    signals_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    initial_capital: float = 1000,
    commission_bps: float = 8.0,
    slippage_bps: float = 5.0
) -> dict:
    # Векторизованная симуляция
    ...
```

2. **Метрики:**
- Sharpe, Sortino, Calmar
- Max Drawdown (величина, duration)
- Win rate, avg win/loss
- Total trades, exposure time

3. **Интеграция с моделями:**
- POST /backtest/run (exchange, symbol, TF, model_path)
- Сравнение с buy-and-hold

**Коммит:**
```bash
git commit -m "feat: add vectorized backtesting engine

- Vectorized simulation via pandas (fast)
- Realistic fees/slippage modeling
- Risk metrics: Sharpe, Sortino, Calmar, Max DD
- Benchmark comparison (buy-and-hold)
- New endpoint: POST /backtest/run"
```

---

### Задача #4: RL-агент (PPO) (Приоритет: СРЕДНИЙ)

**Цель:** Reinforcement Learning для динамического sizing.

#### План

1. **Установка:**
```bash
pip install stable-baselines3>=2.0 gymnasium>=0.28
```

2. **Создать src/rl_env.py:**
- Custom Gym environment
- State: equity, positions, features
- Actions: buy/sell/hold + sizing
- Reward: Sharpe ratio

3. **Обучение:**
- PPO с гиперпараметрами по умолчанию
- Walk-forward training (30-дневные окна)

4. **Интеграция:**
- Hybrid: XGBoost (направление) + RL (sizing)

**Коммит:**
```bash
git commit -m "feat: add RL agent for dynamic position sizing

- Stable-Baselines3 PPO agent
- Custom Gym environment with crypto trading simulation
- Hybrid model: XGBoost (direction) + RL (sizing)
- Training: walk-forward on historical data
- New endpoint: POST /rl/train, POST /rl/predict"
```

---

## 🎯 Задача #1 (ЗАВЕРШЕНО): Декомпозиция main.py (Приоритет: КРИТИЧНО)

**Цель:** Разбить main.py (4000+ строк, 83 эндпоинта) на модульные роутеры.

### Контекст
- **Файл:** `src/main.py` (4030 строк)
- **Проблема:** Монолит, сложно поддерживать
- **Решение:** APIRouter по доменам (News, Prices, Models, Signals, Trade, Risk, Automation, UI, etc.)

### План Действий

#### Шаг 1: Подготовка (15 мин)
1. Создать структуру:
   ```
   src/routers/
   ├── __init__.py
   ├── news.py          # News (6 эндпоинтов)
   ├── prices.py        # Prices (2 эндпоинта)
   ├── dataset.py       # Dataset (1 эндпоинт)
   ├── models.py        # Model (10 эндпоинтов)
   ├── signals.py       # Signal (4 эндпоинта)
   ├── risk.py          # Risk (2 эндпоинта)
   ├── notify.py        # Notify (3 эндпоинта)
   ├── trade.py         # Trade (14 эндпоинтов)
   ├── automation.py    # Automation (2 эндпоинта)
   ├── watchlist.py     # Watchlist (6 эндпоинтов)
   ├── report.py        # Report (2 эндпоинта)
   ├── ui.py            # UI (3 эндпоинта)
   ├── journal.py       # Journal (2 эндпоинта)
   ├── backup.py        # Backup (1 эндпоинт)
   ├── db_admin.py      # DB (3 эндпоинта)
   └── debug.py         # Debug (4 эндпоинта)
   ```

2. Читать `src/main.py` для понимания зависимостей

#### Шаг 2: Выделение роутеров (по одному за раз)

**Пример: News Router**
```python
# src/routers/news.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.db import get_db
from src.main import require_api_key  # временно, потом вынести в src/dependencies.py

router = APIRouter(prefix="/news", tags=["News"])

@router.post("/fetch")
def fetch_news(db: Session = Depends(get_db), _=Depends(require_api_key)):
    # код из main.py
    ...

@router.post("/analyze")
def analyze_news(db: Session = Depends(get_db), _=Depends(require_api_key)):
    ...

# и т.д.
```

**Порядок выделения роутеров (от простого к сложному):**
1. news.py (6 эндпоинтов, независимый)
2. prices.py (2 эндпоинта, зависит от src/prices.py)
3. dataset.py (1 эндпоинт, зависит от src/features.py)
4. report.py (2 эндпоинта, зависит от src/reports.py)
5. watchlist.py (6 эндпоинтов, зависит от src/watchlist.py)
6. risk.py (2 эндпоинта, зависит от src/risk.py)
7. notify.py (3 эндпоинта, зависит от src/notify.py)
8. models.py (10 эндпоинтов, зависит от src/modeling.py, src/champion.py)
9. signals.py (4 эндпоинта, зависит от models, risk, notify)
10. trade.py (14 эндпоинтов, зависит от src/trade.py, signals)
11. automation.py (2 эндпоинта, зависит от всех модулей)
12. ui.py, journal.py, backup.py, db_admin.py, debug.py

#### Шаг 3: Обновление main.py

```python
# src/main.py (после рефакторинга)
from fastapi import FastAPI
from src.routers import news, prices, models, signals, trade, risk, notify, automation, watchlist, report, ui, journal, backup, db_admin, debug

app = FastAPI(...)

# Подключаем роутеры
app.include_router(news.router)
app.include_router(prices.router)
app.include_router(models.router)
app.include_router(signals.router)
app.include_router(trade.router)
app.include_router(risk.router)
app.include_router(notify.router)
app.include_router(automation.router)
app.include_router(watchlist.router)
app.include_router(report.router)
app.include_router(ui.router)
app.include_router(journal.router)
app.include_router(backup.router)
app.include_router(db_admin.router)
app.include_router(debug.router)

# Оставить только:
# - startup/shutdown events
# - middleware
# - корневые эндпоинты (/, /ping)
# - утилиты (require_api_key, get_db и т.д.)
```

#### Шаг 4: Вынос зависимостей
```python
# src/dependencies.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader
import os

API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(x_api_key: Optional[str] = Security(api_key_header)):
    if not API_KEY:
        raise HTTPException(503, detail="Set API_KEY in env")
    if not x_api_key:
        raise HTTPException(401, detail="X-API-Key header required")
    if x_api_key != API_KEY:
        raise HTTPException(401, detail="Invalid API key")
    return True
```

#### Шаг 5: Тестирование
1. Запустить сервер: `uvicorn src.main:app --reload`
2. Проверить Swagger UI: http://127.0.0.1:8000/docs
3. Убедиться, что все эндпоинты работают
4. Прогнать pytest (если есть тесты)

#### Шаг 6: Commit
```bash
git add src/routers/
git add src/main.py
git add src/dependencies.py
git commit -m "refactor: decompose main.py into modular routers

- Created src/routers/ with 15 domain-specific routers
- Moved API endpoints from main.py (4000+ lines → ~300 lines)
- Extracted dependencies to src/dependencies.py
- All endpoints tested and working
- Swagger UI structure preserved"
git push
```

### Ожидаемый Результат
- main.py сократился с 4000+ строк до ~300 строк
- 15 роутеров по доменам (News, Prices, Models, etc.)
- Улучшенная читаемость и поддерживаемость
- Легче писать тесты (изолированные роутеры)

### Риски
- Циклические импорты (решение: src/dependencies.py)
- Нарушение работы эндпоинтов (решение: тщательное тестирование)
- Потеря startup/shutdown логики (решение: оставить в main.py)

### Критерии Успеха
- ✅ Все эндпоинты работают (Swagger UI)
- ✅ Тесты зелёные (если есть)
- ✅ Линтеры без критичных ошибок
- ✅ Код закоммичен и отправлен в GitHub

---

## 🎯 Задача #2: Расширение Тестов (Приоритет: ВЫСОКИЙ)

**Цель:** Coverage >80% для критичных модулей.

### Контекст
- **Текущий coverage:** <5% (только tests/test_cmd_parser.py)
- **Проблема:** Отсутствие автоматических тестов → риск регрессии
- **Решение:** pytest для всех модулей

### План Действий

#### Приоритетные Модули (в порядке важности)
1. **src/modeling.py** — ML пайплайн
2. **src/features.py** — генерация фичей
3. **src/trade.py** — paper trading (критично для безопасности капитала)
4. **src/risk.py** — фильтры сигналов
5. **src/champion.py** — champion/challenger отбор
6. **src/prices.py** — загрузка OHLCV
7. **src/news.py** — парсинг RSS
8. **src/analysis.py** — sentiment-анализ

#### Шаблон Теста

```python
# tests/test_modeling.py
import pytest
import pandas as pd
import numpy as np
from src.modeling import time_split, train_xgb_and_save, load_latest_model

def test_time_split():
    df = pd.DataFrame({"a": range(100)})
    train, test = time_split(df, test_ratio=0.2)
    assert len(train) == 80
    assert len(test) == 20

def test_time_split_small_df():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="dataset too small"):
        time_split(df, test_ratio=0.2)

# Мок для XGBoost обучения
def test_train_xgb_and_save(tmp_path):
    # Подготовка данных
    df = pd.DataFrame({
        "ret_1": np.random.randn(200),
        "ret_3": np.random.randn(200),
        "future_ret": np.random.randn(200),
        "y": np.random.randint(0, 2, 200)
    })
    
    metrics, model_path = train_xgb_and_save(
        df, ["ret_1", "ret_3"], artifacts_dir=str(tmp_path)
    )
    
    assert "accuracy" in metrics
    assert "roc_auc" in metrics
    assert Path(model_path).exists()
```

#### Команды
```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Только конкретный модуль
pytest tests/test_modeling.py -v

# С выводом print
pytest -s
```

#### Commit
```bash
git add tests/
git commit -m "test: add comprehensive test suite for ML and trading modules

- Added tests for modeling.py (train, load, walk-forward CV)
- Added tests for features.py (RSI, BB, news aggregation)
- Added tests for trade.py (auto-sizing, PnL, paper trading)
- Added tests for risk.py (filters, volatility classification)
- Coverage increased from 5% to 82%"
git push
```

---

## 🎯 Задача #3: Исправление Ruff Ошибок (Приоритет: СРЕДНИЙ)

**Цель:** Устранить 46 стилистических ошибок (E701, E702, E722).

### Контекст
- **Ошибки:** 56 (10 исправлено, 46 осталось)
- **Типы:** E701 (multiple statements on one line), E702 (semicolon), E722 (bare except)

### План
1. Читать вывод `ruff check src/`
2. Исправлять по одному файлу:
   - src/champion.py (2 ошибки)
   - src/main.py (30+ ошибок)
   - src/notify.py (5 ошибок)
   - src/prices.py (3 ошибки E741 — ambiguous variable `l`)
   - src/news.py (1 ошибка E711)
   - src/watchlist.py (1 ошибка F841 — unused variable)

3. Запустить `ruff check src/ --fix` для автоисправления
4. Вручную исправить оставшиеся (где --fix не помог)

### Commit
```bash
git add src/
git commit -m "style: fix ruff errors (E701, E702, E722)

- Fixed multiple statements on one line (E701, E702)
- Replaced bare except with explicit Exception (E722)
- Renamed ambiguous variable 'l' to 'low' (E741)
- Removed unused variable 'markets' (F841)
- All ruff checks passing"
git push
```

---

## 🎯 Задача #4: CI/CD Pipeline (Приоритет: СРЕДНИЙ)

**Цель:** Автоматическая проверка кода на GitHub.

### План
Создать `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Lint with ruff
        run: ruff check src/
      
      - name: Format with black
        run: black --check src/
      
      - name: Type check with mypy
        run: mypy src/ --ignore-missing-imports
      
      - name: Run tests
        run: pytest --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 🎯 Задача #5: Миграция на PostgreSQL (Приоритет: НИЗКИЙ, версия 0.9)

**Цель:** Замена SQLite на Postgres для продакшн-готовности.

### План
1. Docker Compose с Postgres 16
2. Обновить src/config.py (переменная DATABASE_URL)
3. Alembic миграции (уже настроено)
4. Тестирование на тестовых данных
5. Миграция данных из SQLite

---

## 📝 Обновление Этого Файла

**После завершения задачи:**
1. Отметить ✅ в секции "Завершено"
2. Обновить docs/CHANGELOG.md
3. Git commit:
   ```bash
   git add docs/NEXT_STEPS.md docs/CHANGELOG.md
   git commit -m "docs: update NEXT_STEPS after completing [task name]"
   ```

---

## 💡 Советы для Новых Чатов

1. **Всегда начинай с чтения документации:**
   - docs/PROJECT_OVERVIEW.md
   - docs/ROADMAP.md
   - docs/NEXT_STEPS.md (этот файл)
   - docs/CHANGELOG.md

2. **Создавай TODO-лист:**
   ```python
   todo_write(merge=False, todos=[
       {"id": "1", "content": "...", "status": "in_progress"},
       ...
   ])
   ```

3. **Делай частые коммиты:**
   - После каждого завершённого шага
   - С понятными сообщениями (conventional commits)

4. **Тестируй изменения:**
   - Запускай сервер локально
   - Проверяй Swagger UI
   - Запускай pytest

5. **Обновляй память:**
   ```python
   update_memory(
       action="create",
       title="Декомпозиция main.py завершена",
       knowledge_to_store="..."
   )
   ```

6. **Проси помощь у пользователя:**
   - Если нужны API ключи
   - Если нужно подтверждение деструктивных операций
   - Если непонятна бизнес-логика

---

**Последнее обновление:** 2025-10-10  
**Ответственный:** AI Assistant (Claude Sonnet 4.5)  
**Статус проекта:** Версия 0.7 → 0.8 (рефакторинг)

