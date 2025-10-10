# 🗺️ Дорожная Карта MyAssistent

## Легенда
- ✅ **Завершено** — функция работает
- 🚧 **В разработке** — активно ведутся работы
- 📋 **Запланировано** — в очереди на реализацию
- 💡 **Идея** — концептуальная стадия

---

## Текущая Версия: 0.7

### ✅ Завершённые Функции

#### Инфраструктура и Backend
- [x] FastAPI + SQLAlchemy + SQLite (12 таблиц)
- [x] APScheduler (7 фоновых задач)
- [x] Swagger UI с X-API-Key авторизацией
- [x] Pydantic валидация конфигурации
- [x] Структурированное логирование (app.log, server.log)
- [x] Trade Guard (kill switch: live/close_only/locked)
- [x] Streamlit UI (временный дашборд)

#### Данные и Интеграции
- [x] OHLCV загрузка (Binance, Bybit) через ccxt
- [x] RSS новости (Cointelegraph, CoinDesk, The Block)
- [x] Канонизация URL (убирает utm_*, дедупликация)
- [x] Sentiment-анализ (лексиконы RU/EN)
- [x] Автотеггинг (btc, eth, etf, sec, hack, regulation, etc.)

#### ML и Модели
- [x] Датасет: RSI, BB, EMA + новости (40+ фич)
- [x] XGBoost с threshold grid search
- [x] Walk-forward cross-validation
- [x] Champion/Challenger отбор (OOS-оценка)
- [x] Реестр активных моделей per pair/TF/horizon
- [x] SLA моделей (max_age_days, retrain_if_auc_below)
- [x] Автоматическое переобучение (job_models_maint)

#### Риск-Менеджмент
- [x] Фильтры сигналов (волатильность, EMA-тренд, объём)
- [x] Волатильность-классификация (dead/normal/hot)
- [x] Cooldown между сигналами (90 мин по умолчанию)
- [x] Лимиты: max_open_positions, position_max_fraction
- [x] Комиссии и проскальзывание в симуляторе
- [x] Мониторинг открытых позиций (partial_at, flat_after)

#### Торговля
- [x] Paper trading (JSON state)
- [x] Auto-sizing от equity с учётом волатильности
- [x] Ручные команды: /buy, /sell, /close
- [x] Equity tracking (история для графиков)
- [x] PnL расчёт (реализованный + нереализованный)

#### Уведомления и Мониторинг
- [x] Telegram Bot API (сигналы, отчёты, алерты)
- [x] Форматирование сообщений (простой/raw стили)
- [x] HTML-отчёты (позиции, сигналы, outcomes)
- [x] News Radar (детектор всплесков новостей)

#### Автоматизация
- [x] Динамический watchlist
- [x] Auto-discovery топ-пар по объёму (ccxt)
- [x] Автоторговля при получении BUY-сигнала
- [x] Ежедневные отчёты (03:50 UTC)

---

## 🚧 Версия 0.8 — Рефакторинг и Стабилизация

**Цель:** Улучшить качество кода, добавить миграции, расширить тесты.

### Backend
- [x] Объединить БД (assistant.db вместо app.db)
- [x] Обновить requirements.txt (ruff, black, mypy, alembic, pytest)
- [ ] Декомпозиция main.py на роутеры:
  - [ ] `src/routers/news.py`
  - [ ] `src/routers/prices.py`
  - [ ] `src/routers/models.py`
  - [ ] `src/routers/signals.py`
  - [ ] `src/routers/trade.py`
  - [ ] `src/routers/risk.py`
  - [ ] `src/routers/automation.py`
- [ ] Alembic миграции (initial schema)
- [ ] Pre-commit хуки (ruff, black, mypy)

### Тестирование
- [ ] Покрытие >80%:
  - [ ] `tests/test_modeling.py` (XGBoost, threshold grid)
  - [ ] `tests/test_features.py` (RSI, BB, новости)
  - [ ] `tests/test_trade.py` (sizing, PnL, auto-buy)
  - [ ] `tests/test_risk.py` (фильтры, волатильность)
  - [ ] `tests/test_champion.py` (OOS, promote)
- [ ] CI/CD (GitHub Actions): lint + test + build

### Документация
- [x] PROJECT_OVERVIEW.md (архитектура, модули)
- [x] ROADMAP.md (этот файл)
- [ ] CHANGELOG.md (версионная история)
- [ ] API.md (OpenAPI Spec, примеры запросов)
- [ ] CONTRIBUTING.md (правила разработки)

### Безопасность
- [ ] Секреты через secrets manager (не в .env)
- [ ] Rate limiting (slowapi)
- [ ] CORS настройки (production-ready)
- [ ] Логирование запросов (audit trail)

**ETA:** 2-3 недели

---

## 📋 Версия 0.9 — Продакшн-готовность

**Цель:** Миграция на PostgreSQL, улучшенный UI, мониторинг.

### База Данных
- [ ] Миграция SQLite → PostgreSQL
  - [ ] Docker Compose с Postgres 16
  - [ ] pgbouncer для connection pooling
  - [ ] Индексы по времени/символу/ТФ
  - [ ] Партиционирование таблицы prices
- [ ] Alembic миграции для всех изменений схемы

### ML Инфраструктура
- [ ] MLflow tracking
  - [ ] Логирование экспериментов (параметры, метрики)
  - [ ] Model registry (production/staging/archived)
  - [ ] Артефакты (features_json, confusion matrix, equity curve)
- [ ] Hyperparameter tuning (Optuna/Ray Tune)
- [ ] Feature store (локальный, файловый)

### UI/UX
- [ ] Next.js + TypeScript frontend
  - [ ] shadcn/ui компоненты
  - [ ] Recharts/ECharts для графиков
  - [ ] React Query для кеширования
  - [ ] Zustand для state management
- [ ] Real-time updates (WebSocket)
- [ ] Мобильная адаптация (responsive)
- [ ] Dark mode

### Мониторинг и Алертинг
- [ ] Prometheus + Grafana
  - [ ] Метрики: latency, throughput, error rate
  - [ ] Дашборды: модели, сигналы, equity
- [ ] Sentry (error tracking)
- [ ] Healthchecks.io (uptime monitoring)

### Оптимизация
- [ ] Кеширование (Redis)
  - [ ] Цены (последние свечи)
  - [ ] Модели (inference результаты)
  - [ ] Конфигурация
- [ ] Async SQLAlchemy
- [ ] Batch processing для новостей

**ETA:** 4-6 недель

---

## 📋 Версия 1.0 — Расширенная Аналитика

**Цель:** Deep Learning для новостей, расширенные фичи, бэктест.

### NLP и Sentiment
- [ ] **FinBERT для sentiment-анализа** 🎯
  - [ ] Hugging Face Transformers (transformers>=4.30)
  - [ ] Модели: `ProsusAI/finbert`, `yiyanghkust/finbert-tone`
  - [ ] GPU-ускорение (CUDA) опционально, CPU поддержка обязательна
  - [ ] Batch inference для эффективности
  - [ ] Интеграция с существующей таблицей `ArticleAnnotation`
  - [ ] Сравнение с текущим лексиконным подходом
  - [ ] Кеширование результатов (избегать повторного анализа)
- [ ] Named Entity Recognition (NER)
  - [ ] Извлечение упоминаний (BTC, ETH, компании, персоны)
  - [ ] Связывание событий с торговыми парами
  - [ ] Учет контекста (позитив/негатив для конкретного актива)
- [ ] Topic modeling (LDA/BERTopic)
  - [ ] Кластеризация новостей по темам
  - [ ] Детектор emerging topics

### Расширенные Фичи (100+ фич)
- [ ] **Технические индикаторы (расширение)** 🎯
  - [ ] MACD, Stochastic, ADX, ATR
  - [ ] Ichimoku Cloud компоненты
  - [ ] Volume-weighted indicators (VWAP, VWMA)
  - [ ] Фракталы Williams
- [ ] **On-chain метрики** 🎯
  - [ ] Glassnode API integration
  - [ ] Exchange net flows (приток/отток с бирж)
  - [ ] Active addresses (сетевая активность)
  - [ ] SOPR (Spent Output Profit Ratio)
  - [ ] MVRV Ratio (Market Value to Realized Value)
  - [ ] Puell Multiple (mining economics)
- [ ] **Social signals** 🎯
  - [ ] Twitter/X mentions (через API v2)
  - [ ] Reddit sentiment (r/cryptocurrency, r/bitcoin)
  - [ ] Google Trends (поисковый интерес)
  - [ ] Fear & Greed Index
- [ ] **Макроэкономические данные** 🎯
  - [ ] CPI (Consumer Price Index)
  - [ ] Federal Reserve rates
  - [ ] DXY (US Dollar Index)
  - [ ] Gold, Oil prices
  - [ ] Treasury yields (10Y, 2Y)
- [ ] Order flow metrics
  - [ ] Bid/ask spreads
  - [ ] Order book depth (top 5-10 levels)
  - [ ] Trade flow imbalance

### Бэктестинг
- [ ] **Векторизованный бэктест** 🎯
  - [ ] Реализация через pandas/numpy (быстро)
  - [ ] Комиссии и проскальзывание (реалистичные модели)
  - [ ] Реалистичная симуляция ликвидности
  - [ ] Учет времени исполнения (latency)
  - [ ] Drawdown analysis (max DD, duration, recovery)
  - [ ] Rolling metrics (30d, 90d, 365d Sharpe)
- [ ] Monte Carlo симуляции
  - [ ] Bootstrap ресэмплинг сделок
  - [ ] Стресс-тестирование (worst-case scenarios)
  - [ ] Confidence intervals для метрик
- [ ] Walk-forward оптимизация
  - [ ] Автоматический подбор гиперпараметров на rolling basis
  - [ ] Out-of-sample валидация на каждом шаге
- [ ] Сравнение с бенчмарками
  - [ ] Buy-and-hold (BTC, ETH)
  - [ ] 60/40 портфель (BTC/stablecoins)
  - [ ] Равновзвешенный портфель топ-10

### Визуализация
- [ ] Equity curve с аннотациями (entries/exits)
- [ ] Feature importance (SHAP values)
- [ ] Confusion matrix по периодам
- [ ] Распределение PnL (histogram, QQ-plot)

**ETA:** 6-8 недель

---

## 📋 Версия 1.1 — Reinforcement Learning

**Цель:** RL-агент для портфельного управления и динамического sizing.

### RL Framework
- [ ] **Stable-Baselines3 (PPO)** 🎯
  - [ ] Установка: `stable-baselines3>=2.0`, `gymnasium>=0.28`
  - [ ] PPO (Proximal Policy Optimization) — baseline
  - [ ] A2C, SAC — альтернативы для сравнения
  - [ ] Tensorboard для мониторинга обучения
- [ ] **Custom Gym environment** 🎯
  - [ ] State space:
    - [ ] Позиции (open positions, sizing)
    - [ ] Equity history (rolling window)
    - [ ] Features (технические + фундаментальные + sentiment)
    - [ ] Risk metrics (volatility, DD, Sharpe)
  - [ ] Action space:
    - [ ] Дискретные: buy/sell/hold (3 действия)
    - [ ] Непрерывные: sizing (0.0-1.0 от доступного капитала)
    - [ ] Hybrid: MultiDiscrete для пар + Box для sizing
  - [ ] Reward function:
    - [ ] Sharpe ratio (risk-adjusted returns)
    - [ ] Sortino ratio (downside deviation penalty)
    - [ ] Calmar ratio (max DD penalty)
    - [ ] Penalty за чрезмерную торговлю (комиссии)
  - [ ] Интеграция с историческими данными (walk-forward симуляция)
- [ ] Offline RL (Conservative Q-Learning)
  - [ ] Обучение на исторических траекториях
  - [ ] Избегание distribution shift

### Портфельное Управление
- [ ] Multi-asset portfolio
  - [ ] Одновременное управление 3-10 парами
  - [ ] Корреляционный анализ
  - [ ] Диверсификация
- [ ] Риск-паритет (risk parity)
  - [ ] Распределение капитала по волатильности
- [ ] Mean-variance оптимизация
  - [ ] Markowitz portfolio theory
  - [ ] Efficient frontier
- [ ] **Динамический sizing (RL-driven)** 🎯
  - [ ] RL-агент принимает решения о размере позиции
  - [ ] Учёт рыночных условий (волатильность, тренд)
  - [ ] Адаптация к изменяющейся среде

### Интеграция
- [ ] **Hybrid модель: XGBoost (сигналы) + RL (sizing)** 🎯
  - [ ] XGBoost генерирует вероятность направления (buy/sell)
  - [ ] RL-агент решает размер позиции и тайминг входа
  - [ ] Совместная оптимизация end-to-end
- [ ] Online learning (continuous training)
  - [ ] Periodic retraining на новых данных
  - [ ] Incremental updates
- [ ] Adversarial validation
  - [ ] Детектор distribution drift
  - [ ] Auto-retraining trigger

**ETA:** 8-12 недель

---

## 📋 Версия 1.2 — Real Trading

**Цель:** Переход на реальную торговлю с минимальными рисками.

### Подготовка
- [ ] Testnet тестирование (Bybit Testnet)
  - [ ] 100+ симуляций
  - [ ] Устойчивая прибыль в тесте
- [ ] Строгий риск-контроль
  - [ ] Position limits (max 5% equity per coin)
  - [ ] Daily loss limit (max -2% equity per day)
  - [ ] Max drawdown threshold (kill switch при -10%)
- [ ] Аудит кода (security review)

### Live Trading
- [ ] Старт с минимальным капиталом (1000 ₽)
- [ ] Постепенное увеличение:
  - [ ] 1000 → 2000 (100% прибыль)
  - [ ] 2000 → 5000 (150% прибыль)
  - [ ] 5000 → 10000 (100% прибыль)
- [ ] Ежедневный мониторинг
- [ ] Incident response plan

### Инфраструктура
- [ ] Failover и резервирование
  - [ ] Автоматический restart при краше
  - [ ] Мониторинг uptime (99.9%)
- [ ] Cloud-хостинг (VPS/AWS)
  - [ ] Ubuntu 22.04 LTS
  - [ ] Docker containers
  - [ ] Nginx reverse proxy
- [ ] Бэкапы
  - [ ] БД (ежедневно, 30 дней retention)
  - [ ] Модели (при каждом обучении)
  - [ ] Конфигурация (git-синхронизация)

### Compliance
- [ ] Налоговая отчётность (журнал сделок)
- [ ] Юридическая консультация (РФ законодательство)
- [ ] KYC/AML compliance (Bybit)

**ETA:** 12-16 недель (после успешного завершения 1.0-1.1)

---

## 💡 Долгосрочные Идеи (2.0+)

### Мобильное Приложение
- [ ] Expo + React Native
- [ ] Push-уведомления
- [ ] Мобильные графики
- [ ] Ручное управление позициями

### Multi-Exchange
- [ ] Binance, OKX, Kraken
- [ ] Арбитраж между биржами
- [ ] Унифицированный paper trading

### Futures & Derivatives
- [ ] Perpetual futures (Bybit)
- [ ] Leverage trading (до 5x)
- [ ] Funding rate арбитраж
- [ ] Options (если доступны)

### DeFi Интеграция
- [ ] On-chain trading (Uniswap, PancakeSwap)
- [ ] Yield farming стратегии
- [ ] Liquid staking (stETH, rETH)

### Social Trading
- [ ] Копирование сигналов (подписка)
- [ ] Лидерборды (ranking по Sharpe)
- [ ] API для сторонних интеграций

### Advanced ML
- [ ] Transformer-based модели (Temporal Fusion Transformer)
- [ ] GAN для синтетических данных
- [ ] Meta-learning (few-shot adaptation)
- [ ] Ensemble (XGBoost + LightGBM + CatBoost + NN)

---

## Метрики Успеха

### Версия 0.8 (Рефакторинг)
- [ ] Test coverage ≥ 80%
- [ ] Ruff/Black/Mypy без ошибок
- [ ] Alembic миграции работают

### Версия 0.9 (Продакшн)
- [ ] PostgreSQL миграция успешна
- [ ] MLflow tracking работает
- [ ] Next.js UI запущен

### Версия 1.0 (Аналитика)
- [ ] FinBERT sentiment работает
- [ ] Бэктест показывает Sharpe > 1.5
- [ ] 40+ фич → 100+ фич

### Версия 1.1 (RL)
- [ ] RL-агент обучен
- [ ] Offline RL превосходит XGBoost
- [ ] Портфельное управление работает

### Версия 1.2 (Live Trading)
- [ ] Testnet: 100+ сделок, win rate > 55%
- [ ] Live: +100% за 3 месяца (при max -10% DD)
- [ ] 99.9% uptime

---

## Приоритеты на Ближайший Месяц

### ✅ Завершено (2025-10-10)
- [x] Декомпозиция main.py (технический долг) ✅
- [x] Alembic миграции (безопасность данных) ✅
- [x] Тесты для modeling.py, features.py, trade.py, risk.py (качество ML) ✅
- [x] CI/CD pipeline (GitHub Actions) ✅
- [x] Документация (PROJECT_OVERVIEW, ROADMAP, API, CHANGELOG) ✅

### 🎯 Новые Приоритеты (Следующий Чат)

1. **Критично:**
   - [ ] **Исправление инфраструктуры запуска** ✅ (завершено в этом чате)
     - [x] Добавлен ENABLE_METRICS в start_server.bat
     - [x] Создан start_all.bat для полного стека
     - [x] Обновлена документация QUICK_START.md
   - [ ] **FinBERT sentiment-анализ** 🎯
     - [ ] Установка transformers, torch
     - [ ] Интеграция в src/analysis.py
     - [ ] Сравнительное тестирование (лексиконы vs FinBERT)
     - [ ] Обновление ArticleAnnotation с FinBERT scores

2. **Важно:**
   - [ ] **Расширенные фичи (40+ → 100+)** 🎯
     - [ ] On-chain метрики (Glassnode API)
     - [ ] Макроэкономические данные (CPI, rates, DXY)
     - [ ] Social signals (Twitter, Reddit, Fear & Greed)
     - [ ] Дополнительные технические индикаторы (MACD, ADX, etc.)
   - [ ] **MLflow tracking** (воспроизводимость)
     - [ ] Запуск через start_all.bat уже работает
     - [ ] Интеграция в src/modeling.py
   - [ ] **Next.js UI** (UX)
     - [ ] Настройка frontend/.env.local ✅
     - [ ] Разработка компонентов (Dashboard, Charts, Settings)

3. **Желательно:**
   - [ ] **Векторизованный бэктестинг** 🎯
     - [ ] Реализация в src/backtest.py
     - [ ] Реалистичная симуляция (комиссии, проскальзывание, latency)
     - [ ] Метрики: Sharpe, Sortino, Calmar, Max DD
     - [ ] Сравнение с бенчмарками
   - [ ] **RL-агент (PPO)** 🎯
     - [ ] Stable-Baselines3 integration
     - [ ] Custom Gym environment
     - [ ] Hybrid модель: XGBoost (направление) + RL (sizing)
   - [ ] Postgres миграция (масштабируемость)
     - [ ] Docker Compose уже настроен
     - [ ] Миграция данных через scripts/migrate_sqlite_to_postgres.py

---

## Связь с CHANGELOG

Все завершённые задачи из этой дорожной карты дублируются в [CHANGELOG.md](CHANGELOG.md) с указанием дат и деталей реализации.

**Последнее обновление:** 2025-10-10

