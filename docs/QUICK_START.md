# 🚀 Quick Start — Запуск MyAssistent v0.9

> **Два режима запуска:**
> 1. **Быстрый старт** (start_server.bat) — только Backend + Streamlit
> 2. **Полный стек** (start_all.bat) — Docker + Backend + Streamlit + Frontend

---

## 📋 Предварительные требования

### Минимальные (для быстрого старта)
- **Python 3.11+**

### Полные (для полного стека)
- **Python 3.11+**
- **Node.js 18+** (для Next.js UI)
- **Docker Desktop** (для PostgreSQL, MLflow, Prometheus, Grafana)
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

## 🚀 Шаг 5: Запуск Приложения

### 🎯 Вариант A: Быстрый старт (рекомендуется для начала)

**Запускает:** Backend API + Streamlit UI (без Docker)

```bash
start_server.bat
```

**Автоматически:**
- ✅ Создаёт venv и устанавливает зависимости
- ✅ Запускает FastAPI на :8000
- ✅ Запускает Streamlit на :8501
- ✅ Открывает браузер

**Доступные сервисы:**
- Backend API: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- Metrics: http://127.0.0.1:8000/metrics ✨
- Streamlit UI: http://localhost:8501

**Что НЕ работает без Docker:**
- ❌ MLflow UI (http://localhost:5000)
- ❌ Prometheus (http://localhost:9090)
- ❌ Grafana (http://localhost:3001)
- ❌ Frontend Dashboard (http://localhost:3000)

---

### 🚀 Вариант B: Полный стек (все функции)

**Запускает:** Docker + Backend + Streamlit + Frontend

**Требования:**
1. Docker Desktop установлен и запущен
2. Node.js 18+ установлен

```bash
start_all.bat
```

**Автоматически:**
- ✅ Проверяет Docker и Node.js
- ✅ Запускает Docker Compose (PostgreSQL, MLflow, Prometheus, Grafana)
- ✅ Запускает Backend API
- ✅ Запускает Streamlit UI
- ✅ Устанавливает npm зависимости
- ✅ Запускает Next.js Frontend
- ✅ Открывает все UI в браузере

**Доступные сервисы:**
- Backend API: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- Metrics: http://127.0.0.1:8000/metrics
- Streamlit UI: http://localhost:8501
- **Frontend Dashboard: http://localhost:3000** 🎨
- **MLflow UI: http://localhost:5000** 📊
- **Prometheus: http://localhost:9090** 📈
- **Grafana: http://localhost:3001** (admin/admin) 📊

---

### 🛠️ Вариант C: Ручной запуск (для разработки)

```bash
# Активация venv
.venv\Scripts\activate

# Backend
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# В другом терминале — Streamlit
streamlit run streamlit_app.py --server.port 8501

# В другом терминале — Frontend (опционально)
cd frontend
npm run dev
```

**Проверка Backend:**
```bash
curl http://localhost:8000/ping
# Ожидается: {"status":"ok"}
```

---

## 🎨 Шаг 6: Настройка Frontend (если запускали вручную)

> **Примечание:** При использовании `start_all.bat` этот шаг выполняется автоматически!

```bash
cd frontend

# Создать .env.local из .env.example
copy .env.example .env.local

# Проверить настройки в .env.local:
# NEXT_PUBLIC_API_URL=http://localhost:8000
# NEXT_PUBLIC_API_KEY=803a29e730b47a595e38836abf8c19d7ef325b5790993e17d25515a47a3fc8b6

# Установить зависимости (первый раз)
npm install

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
# Ожидается: {"status":"ok"}
```

### 2. Prometheus Metrics
```bash
curl http://localhost:8000/metrics
# Должны вернуться метрики в формате Prometheus
```

### 3. MLflow UI (если запущен через start_all.bat)
http://localhost:5000

### 4. Prometheus (если запущен через start_all.bat)
http://localhost:9090
- Проверьте: Status → Targets
- `myassistent-api` должен быть UP (зеленый)

### 5. Grafana (если запущен через start_all.bat)
http://localhost:3001
- Username: `admin`
- Password: `admin` (по умолчанию)
- Dashboards → Browse → MyAssistent Overview

### 6. Next.js Frontend (если запущен через start_all.bat)
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
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "15m"
}
```

### 6. Сгенерировать сигнал (тест)

```
POST /signal/latest
{
  "exchange": "bybit",
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

### Если запускали через start_server.bat или start_all.bat
Просто закройте окна:
- `backend` (FastAPI)
- `streamlit-ui` (Streamlit)
- `nextjs-frontend` (Next.js) — если был запущен

### Docker контейнеры
```bash
# Остановка контейнеров (данные сохраняются)
docker-compose down

# С удалением данных (ОСТОРОЖНО! Удалит БД и метрики)
docker-compose down -v
```

### Проверка запущенных контейнеров
```bash
docker ps
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

### ❌ Ошибка: "API_KEY not set"

Убедитесь, что в `start_server.bat` или `start_all.bat` установлен `API_KEY`.

**Решение:**
- Файлы уже содержат ключ по умолчанию
- Если используете `.env`, проверьте `API_KEY=...`

---

### ❌ /metrics возвращает 404 "Not Found"

**Причина:** Переменная `ENABLE_METRICS` не установлена

**Решение:**
```bash
# В start_server.bat или start_all.bat проверьте:
set ENABLE_METRICS=true
```

Или в `.env`:
```env
ENABLE_METRICS=true
```

---

### ❌ MLflow/Prometheus/Grafana не открываются

**Причина:** Docker контейнеры не запущены

**Решение:**
```bash
# Проверка Docker
docker ps

# Если контейнеры не запущены:
docker-compose up -d postgres mlflow prometheus grafana

# Проверка логов:
docker-compose logs mlflow
docker-compose logs prometheus
docker-compose logs grafana
```

---

### ❌ Grafana показывает "No data"

**Причины:**
1. Prometheus не получает метрики от Backend
2. Backend не экспортирует метрики (ENABLE_METRICS=false)

**Решение:**
```bash
# 1. Проверьте метрики Backend
curl http://localhost:8000/metrics
# Должны вернуться метрики

# 2. Проверьте Prometheus Targets
# Откройте: http://localhost:9090/targets
# myassistent-api должен быть UP (зеленый)

# 3. Если Target DOWN, проверьте prometheus.yml:
# targets: ['host.docker.internal:8000']

# 4. Перезапустите Prometheus:
docker-compose restart prometheus
```

---

### ❌ Frontend не подключается к Backend

**Причина:** Неверные настройки в `frontend/.env.local`

**Решение:**
```bash
cd frontend

# Проверьте .env.local (должен существовать)
type .env.local

# Содержимое должно быть:
# NEXT_PUBLIC_API_URL=http://localhost:8000
# NEXT_PUBLIC_API_KEY=803a29e730b47a595e38836abf8c19d7ef325b5790993e17d25515a47a3fc8b6

# Если файла нет, скопируйте из .env.example:
copy .env.example .env.local

# Перезапустите Frontend:
npm run dev
```

---

### ❌ Docker не запускается

**Причина:** Docker Desktop не установлен или не запущен

**Решение:**
1. Скачайте Docker Desktop: https://www.docker.com/products/docker-desktop
2. Установите и запустите
3. Проверьте: `docker --version`

---

### ❌ Node.js ошибки при запуске Frontend

**Решение:**
```bash
cd frontend

# Удалите node_modules и package-lock.json
rmdir /s node_modules
del package-lock.json

# Переустановите зависимости
npm install

# Запустите снова
npm run dev
```

---

**Последнее обновление:** 2025-10-10  
**Версия:** 0.9


