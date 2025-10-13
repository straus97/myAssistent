# 🚀 Запуск Paper Trading на Ubuntu Сервере

## Быстрая Диагностика

### Шаг 1: Подключитесь к серверу
```bash
ssh root@185.73.215.38
# Пароль: GK7gz9yGq15T
```

### Шаг 2: Перейдите в директорию проекта
```bash
cd /root/myAssistent
```

### Шаг 3: Запустите скрипт диагностики
```bash
# Скопируйте скрипт на сервер (если нужно)
# Или выполните команды вручную ниже
bash server_diagnostics.sh
```

## Ручная Диагностика (пошагово)

### 1. Проверка сервиса
```bash
systemctl status myassistent --no-pager
```
**Должно быть:** `active (running)`

### 2. Проверка Docker
```bash
docker ps
```
**Должно быть:** 4 контейнера (postgres, mlflow, prometheus, grafana)

### 3. Проверка PostgreSQL
```bash
# Количество записей
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT COUNT(*) FROM price;"

# Данные по символам
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT exchange, symbol, timeframe, COUNT(*) as count FROM price GROUP BY exchange, symbol, timeframe ORDER BY count DESC LIMIT 5;"
```

### 4. Тест загрузки данных
```bash
curl -X POST "http://localhost:8000/prices/fetch" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "bybit",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "limit": 100
  }'
```

**Ожидается:** `{"status":"ok","added":100,...}`

### 5. Проверка сохранения данных
```bash
# Подождите 2 секунды, затем проверьте
sleep 2
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT COUNT(*) FROM price WHERE symbol = 'BTC/USDT' AND timeframe = '1h';"
```

**Должно быть:** Количество >= 100

---

## Диагностика Проблемы "Not enough data"

### Проблема: Данные загружаются, но теряются

#### Возможные причины:

1. **Неправильный DATABASE_URL**
   ```bash
   grep DATABASE_URL /root/myAssistent/.env
   ```
   **Должно быть:** `DATABASE_URL=postgresql://myassistent:b7d5e83c415946c5232e5d130f532555cc73d6b1aa69e1429e2a79f5179b265a@localhost:5432/myassistent`

2. **Приложение подключается к SQLite вместо PostgreSQL**
   ```bash
   # Проверьте логи
   journalctl -u myassistent --no-pager -n 50 | grep -i "database\|sqlite\|postgres"
   ```

3. **Проблема с транзакциями БД**
   ```bash
   # Проверьте ошибки в логах
   journalctl -u myassistent --no-pager -n 100 | grep -i "error\|exception\|traceback"
   ```

4. **Разные экземпляры БД (SQLite + PostgreSQL)**
   ```bash
   # Проверьте, нет ли файла assistant.db или app.db
   ls -lh /root/myAssistent/*.db
   ```

---

## Исправление Проблемы

### Решение 1: Пересоздать DATABASE_URL
```bash
cd /root/myAssistent

# 1. Остановить сервис
sudo systemctl stop myassistent

# 2. Остановить Docker
docker-compose down

# 3. Проверить .env
cat .env | grep DATABASE_URL

# 4. Если DATABASE_URL неправильный, исправить:
sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://myassistent:b7d5e83c415946c5232e5d130f532555cc73d6b1aa69e1429e2a79f5179b265a@localhost:5432/myassistent|' .env

# 5. Перезапустить Docker
docker-compose up -d

# 6. Подождать 10 секунд
sleep 10

# 7. Перезапустить сервис
sudo systemctl restart myassistent

# 8. Проверить статус
sudo systemctl status myassistent --no-pager
```

### Решение 2: Проверить src/config.py
```bash
cd /root/myAssistent

# Проверить, откуда берется DATABASE_URL
cat src/config.py | grep -A 5 "DATABASE_URL"

# Должно быть:
# DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./assistant.db")
```

### Решение 3: Проверить src/db.py
```bash
cd /root/myAssistent

# Проверить создание engine
cat src/db.py | grep -A 10 "create_engine"

# Убедиться, что используется DATABASE_URL из .env
```

### Решение 4: Удалить SQLite файлы (если есть)
```bash
cd /root/myAssistent

# Найти SQLite файлы
find . -name "*.db" -type f

# Удалить их (осторожно!)
rm -f assistant.db app.db

# Перезапустить
sudo systemctl restart myassistent
```

---

## Запуск Paper Trading

### После исправления проблемы с данными:

#### 1. Загрузите данные
```bash
curl -X POST "http://localhost:8000/prices/fetch" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "bybit",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "limit": 500
  }'
```

#### 2. Проверьте данные в БД
```bash
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT COUNT(*) FROM price WHERE symbol = 'BTC/USDT';"
```

#### 3. Запустите Paper Monitor
```bash
curl -X POST "http://localhost:8000/paper-monitor/start" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["BTC/USDT"],
    "auto_execute": false,
    "update_interval_minutes": 15
  }'
```

#### 4. Проверьте статус
```bash
curl -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/paper-monitor/status | python3 -m json.tool
```

---

## Проверка Health
```bash
curl -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/health | python3 -m json.tool
```

---

## Логи для Отладки

### Просмотр логов приложения
```bash
# Последние 50 строк
journalctl -u myassistent --no-pager -n 50

# В реальном времени
journalctl -u myassistent -f

# Поиск ошибок
journalctl -u myassistent --no-pager -n 200 | grep -i "error\|exception\|traceback"
```

### Логи Docker PostgreSQL
```bash
docker logs myassistent_postgres --tail 50
```

---

## Критичные Проверки

### ✅ Чеклист перед запуском Paper Trading:

- [ ] Сервис `myassistent` запущен (`active (running)`)
- [ ] Docker контейнеры запущены (4 штуки)
- [ ] PostgreSQL доступен
- [ ] DATABASE_URL правильный в `.env`
- [ ] Данные загружаются и **сохраняются** в PostgreSQL
- [ ] `/health` показывает `ok`
- [ ] Нет ошибок в логах
- [ ] Scheduler работает

### Если все ✅, можно запускать Paper Monitor!

---

## Быстрые Команды для Копирования

```bash
# === ПОДКЛЮЧЕНИЕ ===
ssh root@185.73.215.38
cd /root/myAssistent

# === ПРОВЕРКА СТАТУСА ===
systemctl status myassistent --no-pager
docker ps
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT COUNT(*) FROM price;"

# === ПЕРЕЗАПУСК ===
sudo systemctl restart myassistent
docker-compose restart
sleep 10
systemctl status myassistent --no-pager

# === ЗАГРУЗКА ДАННЫХ ===
curl -X POST "http://localhost:8000/prices/fetch" -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" -H "Content-Type: application/json" -d '{"exchange":"bybit","symbol":"BTC/USDT","timeframe":"1h","limit":500}'

# === ПРОВЕРКА ДАННЫХ ===
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT COUNT(*) FROM price WHERE symbol = 'BTC/USDT';"

# === ЗАПУСК PAPER MONITOR ===
curl -X POST "http://localhost:8000/paper-monitor/start" -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" -H "Content-Type: application/json" -d '{"symbols":["BTC/USDT"],"auto_execute":false}'

# === ПРОВЕРКА СТАТУСА ===
curl -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" http://localhost:8000/paper-monitor/status | python3 -m json.tool

# === ЛОГИ ===
journalctl -u myassistent --no-pager -n 50
journalctl -u myassistent -f
```

---

## 🆘 Если Ничего Не Помогает

### Полный сброс и перезапуск:

```bash
cd /root/myAssistent

# 1. Остановить все
sudo systemctl stop myassistent
docker-compose down -v  # ВНИМАНИЕ: -v удалит все данные!

# 2. Проверить DATABASE_URL
grep DATABASE_URL .env

# 3. Пересоздать БД
docker-compose up -d
sleep 10

# 4. Применить миграции
source .venv/bin/activate
alembic upgrade head
deactivate

# 5. Перезапустить сервис
sudo systemctl restart myassistent

# 6. Загрузить данные заново
curl -X POST "http://localhost:8000/prices/fetch" -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" -H "Content-Type: application/json" -d '{"exchange":"bybit","symbol":"BTC/USDT","timeframe":"1h","limit":500}'

# 7. Проверить
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT COUNT(*) FROM price;"
```

---

**Последнее обновление:** 2025-10-13  
**Для сервера:** Ubuntu 22.04, IP 185.73.215.38

