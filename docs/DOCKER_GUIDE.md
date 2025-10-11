# 🐳 Руководство по Docker для MyAssistant

## 📋 Содержание

1. [Что такое Docker и зачем он нужен](#что-такое-docker)
2. [Проверка Docker Desktop](#проверка-docker-desktop)
3. [Интерфейс Docker Desktop](#интерфейс-docker-desktop)
4. [Запуск системы](#запуск-системы)
5. [Управление контейнерами](#управление-контейнерами)
6. [Проверка работы сервисов](#проверка-работы)
7. [Устранение проблем](#устранение-проблем)

---

## 🎯 Что такое Docker и зачем он нужен

**Docker** — это платформа для запуска приложений в изолированных контейнерах.

**Что мы запускаем в Docker:**
- **PostgreSQL** — база данных для продакшна (мощнее SQLite)
- **MLflow** — отслеживание экспериментов ML (логи обучения, версии моделей)
- **Prometheus** — сбор метрик производительности
- **Grafana** — красивые дашборды с графиками
- **pgBouncer** — connection pooling для PostgreSQL (ускоряет запросы)

**Зачем это нужно:**
- ✅ PostgreSQL быстрее SQLite в 10+ раз (для больших данных)
- ✅ MLflow помогает отслеживать качество моделей
- ✅ Grafana показывает метрики в реальном времени
- ✅ Все запускается одной командой
- ✅ Не засоряет Windows (все изолировано)

---

## ✅ Проверка Docker Desktop

### Шаг 1: Откройте Docker Desktop

1. Нажмите **Win + S** (поиск)
2. Введите "Docker Desktop"
3. Запустите приложение

**Первый запуск может занять 1-2 минуты** (загрузка WSL 2)

### Шаг 2: Проверьте статус

В **левом нижнем углу** должен быть зелёный индикатор:
```
🟢 Docker Desktop is running
```

Если видите:
- 🔴 **Docker Desktop stopped** → нажмите кнопку **Start**
- ⚠️ **WSL 2 installation is incomplete** → установите WSL 2 (см. раздел "Устранение проблем")

### Шаг 3: Проверка в терминале

Откройте PowerShell и выполните:

```powershell
docker --version
docker ps
```

**Ожидаемый результат:**
```
Docker version 4.48.0, build 207573
CONTAINER ID   IMAGE     COMMAND   CREATED   STATUS    PORTS     NAMES
```

Если видите ошибку → Docker Desktop не запущен или не установлен.

---

## 🖥️ Интерфейс Docker Desktop

### Главные разделы

1. **Containers** (Контейнеры):
   - Список запущенных контейнеров
   - Кнопки Start/Stop/Restart
   - Логи каждого контейнера

2. **Images** (Образы):
   - Загруженные образы (postgres, mlflow, grafana и др.)
   - Размер образов
   - Кнопка Pull (скачать новый образ)

3. **Volumes** (Тома):
   - Постоянное хранилище данных
   - `postgres_data` — данные PostgreSQL
   - `mlflow_artifacts` — сохранённые модели MLflow
   - `prometheus_data`, `grafana_data`

4. **Settings** (Настройки):
   - Resources → выделить больше RAM/CPU (рекомендуется 4GB RAM)
   - Docker Engine → конфигурация

### Что нажимать в Docker Desktop

**После запуска start_all.bat:**

1. Перейдите в раздел **Containers**
2. Найдите группу `myAssistent` (5 контейнеров)
3. Проверьте статус:
   - 🟢 **Running** → всё работает
   - 🔴 **Exited** → контейнер упал (см. логи)
   - 🟡 **Starting** → ждёт запуска

**Чтобы посмотреть логи:**
1. Кликните на контейнер (например, `myassistent_postgres`)
2. Откроется вкладка **Logs**
3. Ищите ошибки (красным цветом)

**Чтобы перезапустить контейнер:**
1. Наведите на контейнер
2. Справа появятся кнопки
3. Нажмите ⟳ **Restart**

**Чтобы остановить все контейнеры:**
1. В PowerShell выполните: `docker-compose down`
2. Или в Docker Desktop: выберите группу → **Stop**

---

## 🚀 Запуск системы

### Вариант 1: Полный стек (рекомендуется)

**Запускает всё: Docker + Backend + Streamlit + Next.js**

1. **Откройте PowerShell** в `C:\AI\myAssistent`
2. Выполните:

```powershell
.\start_all.bat
```

**Что произойдёт:**

1. ✅ Проверка Docker (должен быть запущен)
2. ✅ Проверка Node.js (для Next.js)
3. ✅ Создание виртуального окружения Python (если нужно)
4. ✅ Установка зависимостей
5. ✅ Запуск Docker контейнеров:
   - PostgreSQL (порт 5432)
   - pgBouncer (порт 6432)
   - MLflow (порт 5000)
   - Prometheus (порт 9090)
   - Grafana (порт 3001)
6. ⏳ Ожидание 15 секунд (пока БД запустится)
7. ✅ Запуск Backend API (порт 8000)
8. ✅ Запуск Streamlit UI (порт 8501)
9. ✅ Запуск Next.js Frontend (порт 3000)
10. 🌐 Автоматическое открытие браузера

**Откроются окна:**
- Консоль `backend` (не закрывать!)
- Консоль `streamlit-ui` (не закрывать!)
- Консоль `nextjs-frontend` (не закрывать!)
- Браузер с 4 вкладками

### Вариант 2: Только Backend + Streamlit (быстрый)

**Без Docker, использует SQLite**

```powershell
.\start_server.bat
```

**Плюсы:**
- Быстрый запуск (5 секунд)
- Не требует Docker
- Хватит для начальных тестов

**Минусы:**
- Нет MLflow (не логируются эксперименты)
- Нет Grafana (нет графиков метрик)
- SQLite медленнее PostgreSQL

---

## 🎛️ Управление контейнерами

### Основные команды Docker Compose

```powershell
# Запустить все контейнеры
docker-compose up -d

# Запустить только нужные (например, только PostgreSQL и MLflow)
docker-compose up -d postgres pgbouncer mlflow

# Остановить все контейнеры
docker-compose down

# Остановить + удалить volumes (⚠️ удалятся все данные!)
docker-compose down -v

# Посмотреть статус
docker-compose ps

# Посмотреть логи всех контейнеров
docker-compose logs

# Посмотреть логи конкретного контейнера
docker-compose logs postgres
docker-compose logs mlflow -f  # -f = follow (следить в реальном времени)

# Перезапустить контейнер
docker-compose restart postgres

# Остановить контейнер
docker-compose stop grafana

# Запустить остановленный контейнер
docker-compose start grafana
```

### Полезные команды Docker

```powershell
# Список всех контейнеров (даже остановленных)
docker ps -a

# Удалить остановленный контейнер
docker rm myassistent_postgres

# Список образов
docker images

# Удалить неиспользуемые образы
docker image prune

# Очистить всё (контейнеры, образы, volumes)
docker system prune -a --volumes  # ⚠️ Осторожно!

# Посмотреть использование ресурсов
docker stats

# Зайти внутрь контейнера (для отладки)
docker exec -it myassistent_postgres bash
# Внутри контейнера:
psql -U myassistent -d myassistent
\dt  # список таблиц
\q   # выход
exit
```

---

## 🔍 Проверка работы сервисов

### Шаг 1: Проверка Docker контейнеров

```powershell
docker-compose ps
```

**Ожидаемый результат:**

```
NAME                      STATUS    PORTS
myassistent_grafana       Up        0.0.0.0:3001->3000/tcp
myassistent_mlflow        Up        0.0.0.0:5000->5000/tcp
myassistent_pgbouncer     Up        0.0.0.0:6432->5432/tcp
myassistent_postgres      Up        0.0.0.0:5432->5432/tcp
myassistent_prometheus    Up        0.0.0.0:9090->9090/tcp
```

Все должны быть в статусе **Up** (зелёным).

### Шаг 2: Проверка Backend API

Откройте браузер:

```
http://127.0.0.1:8000/docs
```

**Что должно быть:**
- ✅ Swagger UI с 80+ эндпоинтов
- ✅ Группы: News, Prices, Models, Signals, Trade, Risk и др.
- ✅ Зелёная надпись "200 OK" при запросе GET /ping

**Проверочный запрос:**

1. Найдите эндпоинт **GET /ping**
2. Нажмите **Try it out**
3. Нажмите **Execute**
4. Должно вернуться: `{"status":"ok","timestamp":"2025-10-11T..."}`

### Шаг 3: Проверка Streamlit UI

```
http://localhost:8501
```

**Что должно быть:**
- ✅ Панель управления с кнопками
- ✅ Графики (если есть данные)
- ✅ Таблицы новостей и сигналов

### Шаг 4: Проверка Next.js Frontend

```
http://localhost:3000
```

**Что должно быть:**
- ✅ Современный интерфейс
- ⚠️ Может быть "In Development" (разработка ещё идёт)

### Шаг 5: Проверка MLflow

```
http://localhost:5000
```

**Что должно быть:**
- ✅ MLflow UI
- ✅ Вкладки: Experiments, Models, Compare
- ⚠️ Пусто (эксперименты появятся после обучения моделей)

**Как проверить:**
1. Зайдите на http://localhost:5000
2. Перейдите в **Experiments**
3. Если нет экспериментов → нормально (обучите модель через API)

### Шаг 6: Проверка Prometheus

```
http://localhost:9090
```

**Что должно быть:**
- ✅ Prometheus UI
- ✅ Status → Targets → `fastapi` должен быть **UP**

**Проверка метрик:**
1. В поле Query введите: `http_requests_total`
2. Нажмите **Execute**
3. Должны появиться метрики (если делали запросы к API)

### Шаг 7: Проверка Grafana

```
http://localhost:3001
```

**Логин:**
- Username: `admin`
- Password: `admin`

**При первом входе:**
1. Попросит сменить пароль → можете пропустить (Skip)
2. Перейдите в **Dashboards**
3. Должен быть дашборд **MyAssistant Overview**

**Что должно быть на дашборде:**
- ✅ Графики: HTTP Requests, Response Time, Error Rate
- ✅ Gauges: Uptime, Memory Usage
- ⚠️ Данные появятся после нагрузки на API

---

## 🔧 Устранение проблем

### Проблема 1: Docker Desktop не запускается

**Ошибка:**
```
WSL 2 installation is incomplete
```

**Решение:**

1. Откройте PowerShell **от администратора**
2. Выполните:

```powershell
wsl --install
wsl --set-default-version 2
```

3. Перезагрузите компьютер
4. Запустите Docker Desktop

### Проблема 2: Контейнер падает сразу после запуска

**Пример: myassistent_postgres → Exited (1)**

**Решение:**

1. Посмотрите логи:

```powershell
docker logs myassistent_postgres
```

2. Если видите `port is already allocated`:
   - Другое приложение занимает порт (например, другой PostgreSQL)
   - Остановите его или измените порт в `docker-compose.yml`

3. Если видите `permission denied`:
   - Docker не хватает прав
   - Settings → Resources → File Sharing → добавьте `C:\AI\myAssistent`

### Проблема 3: MLflow не запускается

**Ошибка в логах:**
```
ERROR: Could not connect to database
```

**Решение:**

MLflow зависит от PostgreSQL. Проверьте:

```powershell
docker-compose logs postgres
```

Если PostgreSQL не запустился → см. Проблему 2.

### Проблема 4: Нет подключения к PostgreSQL из Backend

**Ошибка в Backend:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Решение:**

1. Проверьте, что PostgreSQL запущен:

```powershell
docker-compose ps postgres
```

2. Проверьте переменную окружения в `.env`:

```env
DATABASE_URL=postgresql://myassistent:SecurePassword2025@localhost:5432/myassistent
```

3. Если используете pgBouncer (порт 6432), убедитесь что он запущен:

```powershell
docker-compose ps pgbouncer
```

### Проблема 5: Docker контейнеры занимают много места

**Проверка:**

```powershell
docker system df
```

**Очистка:**

```powershell
# Удалить неиспользуемые контейнеры
docker container prune

# Удалить неиспользуемые образы
docker image prune -a

# Удалить неиспользуемые volumes (⚠️ удалит данные!)
docker volume prune
```

### Проблема 6: start_all.bat не находит Docker

**Ошибка:**
```
[!] Docker не найден!
```

**Решение:**

1. Убедитесь что Docker Desktop запущен
2. Перезапустите PowerShell
3. Проверьте PATH:

```powershell
$env:Path -split ';' | Select-String docker
```

Должен быть путь: `C:\Program Files\Docker\Docker\resources\bin`

### Проблема 7: "Cannot connect to Docker daemon"

**Решение:**

1. Откройте Docker Desktop
2. Дождитесь полного запуска (зелёный индикатор)
3. Повторите команду

---

## 📊 Рекомендуемая настройка Docker Desktop

### Ресурсы (Settings → Resources)

**Рекомендуется для MyAssistant:**

- **CPUs:** 4 (минимум 2)
- **Memory:** 6 GB (минимум 4 GB)
- **Swap:** 2 GB
- **Disk image size:** 60 GB

**Как изменить:**

1. Docker Desktop → ⚙️ Settings
2. Resources → Advanced
3. Переместите ползунки
4. Нажмите **Apply & Restart**

### Автозапуск

Если хотите, чтобы Docker запускался вместе с Windows:

1. Settings → General
2. ✅ **Start Docker Desktop when you log in**
3. ✅ **Use WSL 2 based engine**

---

## 🎯 Следующие шаги после запуска

### 1. Загрузить данные

```bash
# В Swagger UI (http://127.0.0.1:8000/docs)

POST /prices/fetch
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "limit": 4320  # 6 месяцев для 1h
}
```

### 2. Обучить модель

```bash
POST /model/train
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h"
}
```

### 3. Проверить в MLflow

1. Откройте http://localhost:5000
2. Должен появиться эксперимент
3. Посмотрите метрики: accuracy, AUC, Sharpe

### 4. Запустить бэктест

```bash
POST /backtest/run
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-04-01",
  "end_date": "2025-10-11",
  "initial_capital": 1000
}
```

### 5. Проверить дашборд Grafana

1. Откройте http://localhost:3001
2. Login: admin / admin
3. Dashboards → MyAssistant Overview
4. Должны появиться метрики

---

## 📖 Дополнительные ресурсы

- [Docker Desktop Documentation](https://docs.docker.com/desktop/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [PostgreSQL Docker Hub](https://hub.docker.com/_/postgres)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [Grafana Getting Started](https://grafana.com/docs/grafana/latest/getting-started/)

---

**Последнее обновление:** 2025-10-11  
**Версия:** 1.0  
**Статус:** Готово к использованию ✅

