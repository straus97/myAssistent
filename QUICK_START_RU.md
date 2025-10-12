# 🚀 БЫСТРЫЙ СТАРТ — MyAssistent

## 📊 Текущий статус: ГОТОВ К ИСПОЛЬЗОВАНИЮ!

**Модель:** ПРИБЫЛЬНАЯ (+0.16% return, Sharpe 0.77)  
**UI:** Полностью функциональный Dashboard  
**Версия:** 1.0 (Production-ready)

---

## ⚡ ЗАПУСК ЗА 1 КЛИК

### Вариант 1: Автоматический (рекомендуется)

```bash
start_all.bat
```

**Что произойдёт:**
1. Проверка Docker, Node.js, Python
2. Установка зависимостей (если нужно)
3. Запуск Docker контейнеров
4. Запуск Backend API
5. Запуск Streamlit UI
6. Запуск Next.js Frontend
7. Автоматическое открытие в браузере

---

## 🌐 ДОСТУПНЫЕ СЕРВИСЫ

После запуска `start_all.bat` откроются:

| Сервис | URL | Описание |
|--------|-----|----------|
| **Frontend** | http://localhost:3000 | **НОВЫЙ!** Dashboard с графиками |
| Backend API | http://localhost:8000 | FastAPI (REST API) |
| Swagger UI | http://localhost:8000/docs | Интерактивная документация |
| Streamlit | http://localhost:8501 | Альтернативный UI |
| MLflow | http://localhost:5000 | ML эксперименты |
| Prometheus | http://localhost:9090 | Метрики |
| Grafana | http://localhost:3001 | Дашборды (admin/admin) |

---

## 📋 ТРЕБОВАНИЯ

**Обязательно:**
- ✅ Windows 10/11
- ✅ Docker Desktop (запущен)
- ✅ Python 3.11+ (через py launcher)
- ✅ Node.js 18+

**Опционально:**
- Git (для клонирования репозитория)

---

## 🎯 ПЕРВЫЙ ЗАПУСК

### Шаг 1: Клонирование (если ещё не сделано)

```bash
git clone <your-repo-url>
cd myAssistent
```

### Шаг 2: Настройка .env

```bash
# Если .env не существует:
python setup_env.py

# Или скопируйте вручную:
copy env.example.txt .env
```

**Минимальные настройки в .env:**
```ini
API_KEY=dev_api_key_for_testing_only
DATABASE_URL=sqlite:///./assistant.db
TRADE_MODE=paper
ENABLE_METRICS=true
MLFLOW_TRACKING_URI=http://localhost:5000
```

### Шаг 3: Запуск!

```bash
start_all.bat
```

**Дождитесь открытия 4 окон:**
- `backend` — Backend API (не закрывайте!)
- `streamlit-ui` — Streamlit UI (не закрывайте!)
- `nextjs-frontend` — Next.js Frontend (не закрывайте!)
- Браузер с 4 вкладками

---

## 📊 ЧТО ДАЛЬШЕ?

### 1. Загрузка данных (первый раз)

Откройте Swagger UI: http://localhost:8000/docs

**Шаги:**

1. **Загрузить цены:**
   ```
   POST /prices/fetch
   {
     "exchange": "bybit",
     "symbol": "BTC/USDT",
     "timeframe": "1h",
     "limit": 1000
   }
   ```

2. **Загрузить новости:**
   ```
   POST /news/fetch
   ```

3. **Построить датасет:**
   ```
   POST /dataset/build
   {
     "exchange": "bybit",
     "symbol": "BTC/USDT",
     "timeframe": "1h"
   }
   ```

4. **Обучить модель:**
   ```bash
   # В консоли:
   python scripts/train_dynamic_features_only.py
   ```

5. **Сгенерировать сигнал:**
   ```
   POST /signal/latest
   {
     "exchange": "bybit",
     "symbol": "BTC/USDT",
     "timeframe": "1h",
     "auto_trade": false
   }
   ```

---

### 2. Мониторинг в Dashboard

Откройте: http://localhost:3000

**Что увидите:**
- Portfolio overview (Equity, Cash, Positions, Return)
- Equity curve chart (real-time)
- Open positions table
- Recent signals
- Model health status

---

### 3. Проверка бэктеста

```bash
python scripts/run_backtest.py
```

**Результаты сохраняются в:** `artifacts/backtest/`

---

## ⚠️ TROUBLESHOOTING

### Docker не запускается

```
[!] Docker daemon not running!
```

**Решение:** Запустите Docker Desktop и дождитесь готовности.

---

### Ошибка установки зависимостей

```
[!] Failed to install dependencies
```

**Решение:**
```bash
# Вручную установите:
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

### Frontend не открывается

**Проверка:**
```bash
cd frontend
npm install
npm run dev
```

**Если ошибка с node_modules:**
```bash
rd /s /q node_modules
npm install
```

---

### API Key ошибка

```
{"detail": "Set API_KEY in env"}
```

**Решение:** Проверьте `.env`:
```ini
API_KEY=dev_api_key_for_testing_only
```

---

## 🛑 ОСТАНОВКА СИСТЕМЫ

### Остановка сервисов:

1. Закройте окна: `backend`, `streamlit-ui`, `nextjs-frontend`
2. Остановите Docker:
   ```bash
   docker-compose down
   ```

---

## 📚 ДОПОЛНИТЕЛЬНАЯ ДОКУМЕНТАЦИЯ

- `docs/QUICK_START.md` — детальная инструкция
- `docs/API.md` — описание всех эндпоинтов
- `docs/DOCKER_GUIDE.md` — работа с Docker
- `docs/BEGINNER_GUIDE.md` — для новичков
- `ИТОГИ_СЕССИИ.md` — что было сделано сегодня

---

## ✨ ФИЧИ СИСТЕМЫ

**ML/Trading:**
- ✅ Прибыльная модель (Return +0.16%, Sharpe 0.77)
- ✅ 48 динамичных фичей (Technical + News + Price)
- ✅ Backtest engine (векторизованный)
- ✅ Paper trading (JSON state)
- ✅ RL-агент для sizing (опционально)

**Data:**
- ✅ Бесплатные API (CoinGecko, Reddit, Google Trends)
- ✅ RSS новости с sentiment (FinBERT)
- ✅ 2160 rows (90 дней) оптимальный датасет

**Infrastructure:**
- ✅ Docker (PostgreSQL, MLflow, Prometheus, Grafana)
- ✅ Next.js UI с real-time мониторингом
- ✅ 80+ API endpoints
- ✅ 127 автотестов

---

**Готово к использованию!** 🎉

Запускайте: `start_all.bat`

