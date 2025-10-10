# 🚀 Quick Start — Запуск MyAssistent v0.9

> **Полный стек:** PostgreSQL + MLflow + Next.js + Prometheus + Grafana

---

## 📋 Предварительные требования

- **Python 3.11+**
- **Node.js 18+** (для Next.js UI)
- **Docker Desktop** (для PostgreSQL, MLflow, Grafana)
- **Git**

---

## 🔧 Шаг 1: Установка зависимостей

### Backend (Python)

```bash
# Создаём виртуальное окружение
python -m venv .venv

# Активируем (Windows)
.venv\Scripts\activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

### Frontend (Next.js)

```bash
cd frontend
npm install
cd ..
```

---

## ⚙️ Шаг 2: Настройка окружения

Скопируйте `.env.example` в `.env` и обновите:

```env
# API
API_KEY=your_generated_api_key_here

# Database (выберите один)
# SQLite (по умолчанию):
DATABASE_URL=sqlite:///./assistant.db

# PostgreSQL (рекомендуется):
# DATABASE_URL=postgresql://myassistent:your_password@localhost:6432/myassistent
# USE_PGBOUNCER=true

# PostgreSQL credentials
POSTGRES_PASSWORD=your_secure_password_here

# MLflow
MLFLOW_TRACKING_URI=http://localhost:5000

# Prometheus & Grafana
ENABLE_METRICS=true
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin

# Telegram (обязательно для уведомлений)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

**Генерация API ключа:**
```bash
# Windows PowerShell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | % {[char]$_})
```

---

## 🐘 Шаг 3: Запуск инфраструктуры (Docker)

### Вариант A: Полный стек (PostgreSQL + MLflow + Grafana)

```bash
docker-compose up -d postgres pgbouncer mlflow prometheus grafana
```

Проверка:
```bash
docker ps
# Должны быть запущены:
# - myassistent_postgres (5432)
# - myassistent_pgbouncer (6432)
# - myassistent_mlflow (5000)
# - myassistent_prometheus (9090)
# - myassistent_grafana (3001)
```

### Вариант B: Минимальный (только PostgreSQL)

```bash
docker-compose up -d postgres pgbouncer
```

### Вариант C: SQLite (без Docker)

Пропустите этот шаг, используйте `DATABASE_URL=sqlite:///./assistant.db` в `.env`

---

## 🗄️ Шаг 4: Миграция базы данных

### Если используете PostgreSQL:

1. **Применить Alembic миграции:**
```bash
alembic upgrade head
```

2. **Мигрировать данные из SQLite (опционально):**
```bash
python scripts/migrate_sqlite_to_postgres.py
```

### Если используете SQLite:

Миграции применятся автоматически при первом запуске.

---

## 🚀 Шаг 5: Запуск Backend

### Вариант A: Через start_server.bat (Windows)

```bash
start_server.bat
```

Автоматически:
- Активирует .venv
- Установит зависимости (если нужно)
- Запустит FastAPI на :8000
- Запустит Streamlit на :8501

### Вариант B: Вручную

```bash
.venv\Scripts\activate
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

**Проверка:**
- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/ping

---

## 🎨 Шаг 6: Запуск Frontend (Next.js)

```bash
cd frontend

# Создать .env.local
cp .env.example .env.local

# Обновить:
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=your_api_key_from_backend

# Запуск
npm run dev
```

**Проверка:**
- Dashboard: http://localhost:3000

---

## 📊 Шаг 7: Проверка сервисов

### 1. Backend API
```bash
curl http://localhost:8000/ping
# {"status":"ok"}
```

### 2. MLflow UI
http://localhost:5000

### 3. Prometheus
http://localhost:9090

### 4. Grafana
http://localhost:3001
- Username: `admin`
- Password: (из `.env` GRAFANA_PASSWORD)

### 5. Next.js Dashboard
http://localhost:3000

---

## 🎯 Шаг 8: Первоначальная настройка

### 1. Настроить Telegram уведомления

**Swagger UI** → `POST /notify/config`
```json
{
  "on_buy": true,
  "on_sell": true,
  "on_error": true,
  "style": "simple"
}
```

**Тест:**
```
POST /notify/test
```

### 2. Настроить риск-политику

**Swagger UI** → `POST /risk/policy`
```json
{
  "min_prob_gap": 0.05,
  "cooldown_minutes": 180,
  "max_open_positions": 3,
  "buy_fraction": 0.05
}
```

### 3. Загрузить первые данные

```
POST /prices/fetch?symbol=BTC/USDT&timeframe=15m&limit=1000
POST /news/fetch
POST /news/analyze
```

### 4. Построить датасет

```
POST /dataset/build?symbol=BTC/USDT&timeframe=15m
```

### 5. Обучить модель

```
POST /model/train
{
  "exchange": "binance",
  "symbol": "BTC/USDT",
  "timeframe": "15m"
}
```

### 6. Сгенерировать сигнал (тест)

```
POST /signal/latest
{
  "exchange": "binance",
  "symbol": "BTC/USDT",
  "timeframe": "15m",
  "auto_trade": false
}
```

---

## 🔄 Автоматизация (APScheduler)

Автоматические задачи запускаются по расписанию:

| Задача | Интервал | Описание |
|--------|----------|----------|
| Цены | 3 мин | Загрузка OHLCV |
| Новости | 5 мин | RSS fetch |
| Анализ новостей | 10 мин | Sentiment |
| Модели | 03:20 UTC | Переобучение |
| Сигналы | 5 мин | Генерация |
| Отчёт | 03:50 UTC | Ежедневный |

**Ручной запуск:**
```
POST /automation/run
{
  "job": "fetch_prices"
}
```

**Проверка статуса:**
```
GET /automation/status
```

---

## 🛑 Остановка сервисов

### Backend
```bash
# Ctrl+C в терминале где запущен uvicorn
```

### Frontend
```bash
# Ctrl+C в терминале где запущен npm run dev
```

### Docker
```bash
docker-compose down

# С удалением данных (осторожно!):
docker-compose down -v
```

---

## 📚 Дополнительные ресурсы

- **Документация для новичков:** `docs/BEGINNER_GUIDE.md`
- **Миграция на PostgreSQL:** `docs/POSTGRESQL_MIGRATION.md`
- **Готовность к продакшну:** `docs/PRODUCTION_READINESS.md`
- **API справочник:** `docs/API.md`
- **Дорожная карта:** `docs/ROADMAP.md`

---

## 🆘 Troubleshooting

### Ошибка: "API_KEY not set"

Убедитесь, что `.env` содержит `API_KEY=...` и перезапустите сервер.

### Ошибка: "Connection refused" (PostgreSQL)

```bash
# Проверка запущен ли Docker
docker ps | grep postgres

# Если нет, запустите:
docker-compose up -d postgres
```

### Ошибка: "MLflow tracking error"

Проверьте, что MLflow запущен:
```bash
docker ps | grep mlflow
# Если нет:
docker-compose up -d mlflow
```

### Frontend не подключается к Backend

Проверьте `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_KEY=<тот же ключ что и в backend .env>
```

---

**Последнее обновление:** 2025-10-10  
**Версия:** 0.9


