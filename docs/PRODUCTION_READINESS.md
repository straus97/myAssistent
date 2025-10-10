# 🚀 Готовность к Продакшну — Чеклист перед реальной торговлей

> **КРИТИЧНО:** Этот документ защитит вас от потери капитала. Не пропускайте шаги!

---

## 📋 Оглавление

1. [Готовность системы (Version 0.9+)](#-готовность-системы-version-09)
2. [Тестирование Paper Trading](#-тестирование-paper-trading)
3. [Миграция на PostgreSQL](#-миграция-на-postgresql)
4. [Мониторинг и алертинг](#-мониторинг-и-алертинг)
5. [Инфраструктура](#-инфраструктура)
6. [Testnet проверка](#-testnet-проверка)
7. [Live Trading checklist](#-live-trading-checklist)
8. [Когда НЕ торговать](#-когда-не-торговать)

---

## ✅ Готовность системы (Version 0.9+)

### Обязательные компоненты

- [ ] **PostgreSQL вместо SQLite**
  - Причина: SQLite не подходит для конкурентных записей
  - Решение: `docker-compose up -d postgres`
  - Проверка: `DATABASE_URL` в `.env` указывает на PostgreSQL

- [ ] **MLflow Tracking**
  - Причина: Воспроизводимость экспериментов
  - Решение: Настроить MLflow server
  - Проверка: Логи моделей сохраняются в MLflow

- [ ] **Мониторинг (Prometheus + Grafana)**
  - Причина: Реал-тайм алерты при сбоях
  - Решение: `docker-compose up -d prometheus grafana`
  - Проверка: Дашборды работают

- [ ] **Error tracking (Sentry)**
  - Причина: Мгновенные уведомления об ошибках
  - Решение: Интеграция Sentry SDK
  - Проверка: Тестовое исключение попало в Sentry

- [ ] **Healthchecks.io**
  - Причина: Алерты, если сервер упал
  - Решение: Регистрация + cron ping каждые 5 минут
  - Проверка: Пропущенный ping → email/SMS

---

## 🧪 Тестирование Paper Trading

### Минимальные требования (3 месяца)

| Метрика | Минимум | Хорошо | Отлично |
|---------|---------|--------|---------|
| **Total Return** | +10% | +25% | +50% |
| **Sharpe Ratio** | 1.5 | 2.0 | 3.0+ |
| **Max Drawdown** | < 15% | < 10% | < 5% |
| **Win Rate** | > 50% | > 55% | > 60% |
| **Profit Factor** | > 1.3 | > 1.5 | > 2.0 |
| **Количество сделок** | 100+ | 200+ | 500+ |

### Условия успеха

1. **Стабильная прибыль 12 недель подряд**
   - Нет недель с убытком > -5%
   - Equity растёт монотонно
   - Drawdown восстанавливается < 2 недель

2. **Diversification**
   - Торгуете минимум 5 пар (BTC, ETH, SOL, DOGE, BNB)
   - Прибыль не зависит от одной пары
   - Корреляция < 0.7

3. **Устойчивость к волатильности**
   - Протестировали падение > -20% за день
   - Протестировали рост > +30% за день
   - Kill switch сработал корректно

4. **Без переоптимизации (overfitting)**
   - Walk-forward CV показывает Sharpe > 1.5
   - OOS метрики не хуже IS на > 20%
   - Модели работают на новых данных

---

## 🐘 Миграция на PostgreSQL

### Почему критично

| Проблема SQLite | Решение PostgreSQL |
|-----------------|---------------------|
| Блокировки при записи | Конкурентные транзакции |
| Нет партиционирования | Партиции по времени (prices) |
| Медленный поиск | GIN/GiST индексы |
| Файл > 50 MB в git | Серверная БД |
| Нет репликации | Streaming replication |

### Чеклист миграции

- [ ] Docker Compose запущен: `docker-compose up -d postgres pgbouncer`
- [ ] Проверка подключения: `psql -h localhost -U myassistent -d myassistent`
- [ ] Alembic миграции применены: `alembic upgrade head`
- [ ] Данные мигрированы: `python scripts/migrate_sqlite_to_postgres.py`
- [ ] Индексы созданы (проверка: `\di` в psql)
- [ ] Connection pooling работает (проверка логов: "pool size = 20")

### После миграции

```bash
# Проверка размера БД
psql -U myassistent -d myassistent -c "SELECT pg_size_pretty(pg_database_size('myassistent'))"

# Проверка индексов
psql -U myassistent -d myassistent -c "\di+"

# Vacuum для оптимизации
psql -U myassistent -d myassistent -c "VACUUM ANALYZE"
```

---

## 📊 Мониторинг и алертинг

### Обязательные метрики

#### Системные
- **CPU usage** < 80%
- **Memory usage** < 85%
- **Disk space** > 20 GB свободно
- **DB connections** < 80% от pool_size

#### Приложение
- **Latency (p99)** < 500ms для всех эндпоинтов
- **Error rate** < 1%
- **Model staleness** < 7 дней
- **Signal generation rate** > 0 в день

#### Торговля
- **Equity** (real-time tracking)
- **Drawdown** (alert если > 10%)
- **Open positions** (alert если > max_open_positions)
- **PnL** (дневной, недельный, месячный)

### Настройка алертов

```yaml
# Пример для Prometheus Alertmanager
groups:
  - name: trading
    rules:
      - alert: HighDrawdown
        expr: current_drawdown_pct > 10
        for: 5m
        annotations:
          summary: "Drawdown превысил 10%!"
          
      - alert: ModelStale
        expr: (time() - model_last_trained_timestamp) / 86400 > 7
        annotations:
          summary: "Модель не обучалась 7+ дней"
          
      - alert: NoSignals24h
        expr: signals_generated_24h == 0
        annotations:
          summary: "Не было сигналов 24 часа"
```

---

## 🏗️ Инфраструктура

### Cloud Deployment (обязательно для live)

**Проблема локального запуска:**
- ПК может выключиться (Windows Update)
- Нет резервирования
- Uptime < 99%

**Решение: VPS/Cloud**

#### Рекомендуемые провайдеры

| Провайдер | CPU/RAM | Цена/мес | Uptime SLA |
|-----------|---------|----------|------------|
| **DigitalOcean** | 2 vCPU, 4 GB | $24 | 99.99% |
| **Hetzner** | 2 vCPU, 4 GB | €4.51 | 99.9% |
| **AWS Lightsail** | 2 vCPU, 4 GB | $24 | 99.99% |

#### Минимальные требования

- **OS:** Ubuntu 22.04 LTS
- **CPU:** 2+ vCPU
- **RAM:** 4+ GB
- **Disk:** 50 GB SSD
- **Network:** 100 Mbps+

### Docker Compose production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    build: .
    restart: always
    environment:
      ENV: production
      DATABASE_URL: postgresql://user:pass@postgres:5432/myassistent
    depends_on:
      - postgres
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/ping"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  postgres:
    image: postgres:16-alpine
    restart: always
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready"]
      interval: 10s
  
  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
```

### Backup strategy

- **БД:** Ежедневно в 4:00 UTC
- **Модели:** После каждого обучения
- **Конфигурация:** Git sync каждые 12 часов
- **Retention:** 30 дней daily, 12 месяцев monthly

```bash
# Пример cron backup
0 4 * * * pg_dump myassistent | gzip > /backups/db_$(date +\%Y\%m\%d).sql.gz
0 4 * * * tar -czf /backups/models_$(date +\%Y\%m\%d).tar.gz artifacts/models/
```

---

## 🧪 Testnet проверка

### Bybit Testnet setup

1. Регистрация: https://testnet.bybit.com
2. Получите testnet API keys
3. Обновите `.env`:
   ```env
   BYBIT_API_KEY=your_testnet_key
   BYBIT_API_SECRET=your_testnet_secret
   BYBIT_TESTNET=true
   ```

### Чеклист тестирования

- [ ] **100+ сделок на testnet**
  - Минимум 2 недели торговли
  - Все типы ордеров: market, limit
  - Все действия: buy, sell, close

- [ ] **Прибыльность**
  - Total return > +15%
  - Sharpe ratio > 2.0
  - Max drawdown < 10%

- [ ] **Технические проблемы**
  - Нет ошибок API (rate limits, authentication)
  - Latency < 500ms
  - Все ордера исполняются

- [ ] **Стресс-тест**
  - 10+ открытых позиций одновременно
  - Быстрые закрытия (< 1 секунда)
  - Работа во время волатильности (падение > 10%)

- [ ] **Kill switch**
  - Протестировали `close_only` (закрылись все позиции)
  - Протестировали `locked` (ничего не происходит)
  - Ручное вмешательство работает

---

## 🚀 Live Trading checklist

### Pre-flight checks (за день до)

- [ ] Paper trading profitable 3+ месяца
- [ ] Testnet успешен (100+ сделок)
- [ ] PostgreSQL migration завершена
- [ ] Мониторинг настроен (Grafana + Sentry)
- [ ] Backup strategy работает
- [ ] Kill switch протестирован
- [ ] Risk policy консервативная (`buy_fraction < 0.05`)
- [ ] Max drawdown < 10% за 3 месяца
- [ ] Капитал, который не жалко потерять

### Day 1: Минимальный капитал

**Рекомендация: 5000-10000 ₽**

Настройки:
```json
{
  "max_open_positions": 1,
  "buy_fraction": 0.05,
  "min_prob_gap": 0.08,
  "cooldown_minutes": 360
}
```

### Week 1: Наблюдение

- Проверяйте каждый день:
  - Equity (растёт?)
  - Позиции (закрываются вовремя?)
  - Логи (ошибки?)
  - Telegram (уведомления приходят?)

- **Если убыток > -5%:**
  - Переключите в `close_only`
  - Проанализируйте причины
  - Вернитесь к paper trading

### Month 1: Оценка

| Метрика | Цель |
|---------|------|
| Total return | > +5% |
| Max drawdown | < 5% |
| Win rate | > 50% |
| Ошибок API | 0 |
| Uptime | > 99% |

**Если цели достигнуты:**
- Увеличьте капитал до 20000 ₽
- `max_open_positions: 2`
- `buy_fraction: 0.08`

**Если НЕ достигнуты:**
- Вернитесь к paper trading
- Анализируйте ошибки
- Улучшайте модель

### Month 3+: Scaling

```
5,000₽ → 10,000₽ (+100%) → 20,000₽ (+100%) → 50,000₽ (+150%)
```

**Правило:** Увеличивайте капитал только при:
- Прибыль > +20% за предыдущий период
- Sharpe ratio > 2.0
- Max drawdown < 8%

---

## ⛔ Когда НЕ торговать

### Рыночные условия

- ❌ **Низкая ликвидность** (volume < $10M за 24h)
- ❌ **Dead volatility** (ATR < 0.5% за 24h)
- ❌ **Экстремальная волатильность** (intraday swing > 20%)
- ❌ **Flash crash** (падение > 15% за 10 минут)
- ❌ **Биржевые проблемы** (API downtime, delisting)

### Системные проблемы

- ❌ **Модель stale** (> 7 дней без обучения)
- ❌ **Метрики упали** (AUC < 0.55, Sharpe < 1.0)
- ❌ **БД проблемы** (запросы > 1 секунда)
- ❌ **Сервер перегружен** (CPU > 90%, RAM > 95%)
- ❌ **Нет мониторинга** (Grafana down, Sentry offline)

### Личные обстоятельства

- ❌ **Отпуск** (некому мониторить)
- ❌ **Стресс** (импульсивные решения)
- ❌ **Потеря > 10%** (эмоции берут верх)
- ❌ **Не понимаете, что происходит** (изучите сначала)

---

## 📈 Roadmap к profitable trading

```
┌─────────────────────────────────────────────────────────┐
│ Version 0.8: Paper Trading + Оптимизация (2-3 месяца)  │
│  - SQLite, локально на ПК                               │
│  - Стабилизация моделей                                 │
│  - Тестирование сигналов                                │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Version 0.9: PostgreSQL + Мониторинг (1 месяц)         │
│  - Миграция на PostgreSQL                               │
│  - MLflow tracking                                      │
│  - Prometheus + Grafana                                 │
│  - Sentry integration                                   │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Version 1.0: Advanced ML (1-2 месяца)                  │
│  - FinBERT для новостей                                 │
│  - Расширенные фичи (40+ → 100+)                        │
│  - Бэктестинг с реалистичной симуляцией                 │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Version 1.1: Reinforcement Learning (2 месяца)         │
│  - RL-агент для sizing                                  │
│  - Портфельное управление                               │
│  - Hybrid XGBoost + RL                                  │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Version 1.2: Testnet проверка (1 месяц)                │
│  - Bybit Testnet: 100+ сделок                           │
│  - Прибыль > +20%                                       │
│  - Нет технических проблем                              │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 🚀 LIVE TRADING: Старт с 5000₽ (осторожно!)            │
│  - Первый месяц: наблюдение                             │
│  - Scaling при прибыли                                  │
│  - Постоянный мониторинг                                │
└─────────────────────────────────────────────────────────┘
```

**Итого: 8-12 месяцев от старта до live trading**

---

## ⚠️ Дисклеймер

**ЭТОТ СОФТ ПРЕДОСТАВЛЯЕТСЯ "КАК ЕСТЬ" БЕЗ КАКИХ-ЛИБО ГАРАНТИЙ.**

Торговля криптовалютами сопряжена с высоким риском. Вы можете потерять весь капитал.

Не инвестируйте больше, чем можете позволить себе потерять.

Автор не несёт ответственности за финансовые потери.

Изучите законы вашей страны (налоги, регулирование).

---

**Последнее обновление:** 2025-10-10  
**Версия:** 0.9  
**Автор:** AI Assistant


