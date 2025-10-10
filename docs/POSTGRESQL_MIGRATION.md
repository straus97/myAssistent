# 🐘 Миграция на PostgreSQL — Пошаговое Руководство

> **Цель:** Переход с SQLite на PostgreSQL для продакшн-готовности  
> **Время:** ~30 минут  
> **Версия:** 0.9

---

## 📋 Содержание

1. [Зачем мигрировать](#-зачем-мигрировать)
2. [Подготовка](#-подготовка)
3. [Запуск PostgreSQL](#-запуск-postgresql)
4. [Миграция данных](#-миграция-данных)
5. [Проверка](#-проверка)
6. [Откат (если что-то пошло не так)](#-откат-если-что-то-пошло-не-так)

---

## 🤔 Зачем мигрировать

### Проблемы SQLite

| Проблема | Влияние | Частота |
|----------|---------|---------|
| **Блокировки при записи** | APScheduler зависает | Ежедневно |
| **Файл в git (52 MB)** | Медленный push/pull | Каждый коммит |
| **Медленный поиск** | `/news/search` > 2 сек | При больших объёмах |
| **Нет репликации** | Потеря данных при сбое | Риск |

### Преимущества PostgreSQL

- ✅ Конкурентные транзакции (APScheduler не блокируется)
- ✅ GIN индексы (поиск новостей < 100 мс)
- ✅ Партиционирование (таблица prices масштабируется)
- ✅ Репликация (streaming replication для HA)
- ✅ Connection pooling через pgbouncer

---

## 🛠️ Подготовка

### Шаг 1: Обновите requirements.txt

Убедитесь, что есть:
```txt
psycopg2-binary>=2.9.9
```

Установите:
```bash
.venv\Scripts\activate
pip install psycopg2-binary
```

### Шаг 2: Сделайте backup SQLite

```bash
# Windows PowerShell
Copy-Item assistant.db assistant.db.backup
```

### Шаг 3: Проверьте Docker

```bash
docker --version
# Должно быть: Docker version 20.10+
```

Если нет: https://docs.docker.com/desktop/install/windows-install/

---

## 🐘 Запуск PostgreSQL

### Шаг 1: Настройте пароли

Создайте `.env` (если ещё нет):
```env
POSTGRES_PASSWORD=your_secure_password_here
PGADMIN_PASSWORD=admin
```

**⚠️ ВАЖНО:** Смените `your_secure_password_here` на надёжный пароль!

### Шаг 2: Запустите Docker Compose

```bash
docker-compose up -d postgres pgbouncer
```

Вы увидите:
```
[+] Running 3/3
 ✔ Network myassistent_network  Created
 ✔ Container myassistent_postgres  Started
 ✔ Container myassistent_pgbouncer  Started
```

### Шаг 3: Проверьте запуск

```bash
docker ps
```

Должны быть запущены:
- `myassistent_postgres` (порт 5432)
- `myassistent_pgbouncer` (порт 6432)

### Шаг 4: Проверьте подключение

```bash
# Через psql (если установлен)
psql -h localhost -p 5432 -U myassistent -d myassistent

# Через docker exec
docker exec -it myassistent_postgres psql -U myassistent -d myassistent
```

Введите пароль из `.env` (POSTGRES_PASSWORD).

Если подключились успешно, увидите:
```
psql (16.0)
Type "help" for help.

myassistent=#
```

Выход: `\q`

---

## 🔄 Миграция данных

### Шаг 1: Обновите .env для миграции

Временно добавьте:
```env
POSTGRES_URL=postgresql://myassistent:your_password@localhost:5432/myassistent
```

Замените `your_password` на ваш POSTGRES_PASSWORD.

### Шаг 2: Примените Alembic миграции

```bash
.venv\Scripts\activate
alembic upgrade head
```

Вы увидите:
```
INFO  [alembic.runtime.migration] Running upgrade  -> 1c717f354547, initial schema
INFO  [alembic.runtime.migration] Running upgrade 1c717f354547 -> 45780899b185, add_postgresql_indexes_and_partitioning
✅ PostgreSQL indexes and optimizations applied
```

### Шаг 3: Запустите скрипт миграции

```bash
python scripts/migrate_sqlite_to_postgres.py
```

Вы увидите:
```
⚠️  ВНИМАНИЕ: Эта операция мигрирует данные из SQLite в PostgreSQL
   SQLite: C:\AI\myAssistent\assistant.db
   PostgreSQL: postgresql://myassistent:***@localhost:5432/myassistent

Продолжить? (yes/no):
```

Введите `yes` и нажмите Enter.

**Ход миграции:**
```
🚀 Начинается миграция SQLite → PostgreSQL
📦 Миграция таблицы: messages
  📊 Всего строк: 0
  ⚠️  Таблица messages пуста, пропускаем

📦 Миграция таблицы: articles
  📊 Всего строк: 1,234
  articles: 100%|████████████████████| 1234/1234 [00:05<00:00, 245 rows/s]
  ✅ Мигрировано: 1,234 строк

📦 Миграция таблицы: prices
  📊 Всего строк: 45,678
  prices: 100%|████████████████████| 45678/45678 [01:23<00:00, 550 rows/s]
  ✅ Мигрировано: 45,678 строк

...

🎉 Миграция завершена успешно!

📊 Статистика миграции:
  messages                          0 строк
  articles                      1,234 строк
  prices                       45,678 строк
  model_runs                       89 строк
  signal_events                   345 строк
  ...
```

### Шаг 4: Обновите .env для приложения

Замените:
```env
DATABASE_URL=sqlite:///./assistant.db
```

На:
```env
# Через pgbouncer (рекомендуется):
DATABASE_URL=postgresql://myassistent:your_password@localhost:6432/myassistent
USE_PGBOUNCER=true

# Или напрямую:
# DATABASE_URL=postgresql://myassistent:your_password@localhost:5432/myassistent
```

### Шаг 5: Перезапустите приложение

```bash
# Остановите старый сервер (Ctrl+C)

# Запустите заново
start_server.bat
```

---

## ✅ Проверка

### 1. Проверьте логи

Откройте `logs/app.log`, найдите:
```
INFO  [src.db] Database engine created: postgresql
INFO  [src.db] Connection pool size: 20
```

### 2. Проверьте Swagger UI

Откройте http://127.0.0.1:8000/docs

Попробуйте:
- `GET /news/latest` — должны вернуться статьи
- `GET /prices/latest` — должны вернуться свечи
- `GET /trade/equity` — должен вернуться баланс

### 3. Проверьте производительность

```bash
# В psql
docker exec -it myassistent_postgres psql -U myassistent -d myassistent

# Проверка индексов
\di+

# Вы должны увидеть:
# ix_articles_title_trgm
# ix_prices_symbol_ts
# ix_signal_events_created_at
# и т.д.

# Проверка размера БД
SELECT pg_size_pretty(pg_database_size('myassistent'));

# Пример вывода: 15 MB
```

### 4. Тест производительности поиска

Swagger UI → `GET /news/search?q=bitcoin&limit=50`

**До миграции (SQLite):** ~2-3 секунды  
**После миграции (PostgreSQL + GIN):** ~50-100 мс

---

## 🔙 Откат (если что-то пошло не так)

### Вариант 1: Вернуться на SQLite

1. Остановите приложение (Ctrl+C)

2. Обновите `.env`:
   ```env
   DATABASE_URL=sqlite:///./assistant.db
   ```

3. Убедитесь, что backup есть:
   ```bash
   # Windows PowerShell
   Test-Path assistant.db.backup
   # Должно вернуть: True
   ```

4. Перезапустите:
   ```bash
   start_server.bat
   ```

### Вариант 2: Пересоздать PostgreSQL

```bash
# Остановите контейнеры
docker-compose down

# Удалите данные
docker volume rm myassistent_postgres_data

# Запустите заново
docker-compose up -d postgres pgbouncer

# Повторите миграцию
python scripts/migrate_sqlite_to_postgres.py
```

---

## 🎯 Следующие шаги

После успешной миграции:

1. **Мониторинг:**
   - Установите pgAdmin: `docker-compose --profile tools up -d pgadmin`
   - Откройте: http://localhost:5050
   - Логин: `admin@myassistent.local` / пароль из `.env`

2. **Бэкапы:**
   ```bash
   # Настройте ежедневный backup
   # (Windows Task Scheduler или cron на VPS)
   
   docker exec myassistent_postgres pg_dump -U myassistent myassistent | gzip > backup_$(date +%Y%m%d).sql.gz
   ```

3. **Оптимизация:**
   ```sql
   -- Регулярно запускайте VACUUM ANALYZE
   VACUUM ANALYZE;
   
   -- Проверяйте статистику
   SELECT * FROM pg_stat_user_tables;
   ```

4. **Партиционирование (опционально):**
   - См. комментарии в `alembic/versions/45780899b185_*.py`
   - Раскомментируйте секцию партиционирования
   - Примените: `alembic upgrade head`

---

## 📚 Дополнительные ресурсы

- [PostgreSQL документация](https://www.postgresql.org/docs/16/)
- [pgbouncer настройка](https://www.pgbouncer.org/config.html)
- [Оптимизация PostgreSQL](https://wiki.postgresql.org/wiki/Performance_Optimization)

---

## 🆘 Проблемы и решения

### Ошибка: "psycopg2 not found"

```bash
pip install psycopg2-binary
```

### Ошибка: "Connection refused"

Проверьте, что контейнер запущен:
```bash
docker ps | grep postgres
```

Если нет, запустите:
```bash
docker-compose up -d postgres
```

### Ошибка: "Authentication failed"

Проверьте пароль в `.env` (POSTGRES_PASSWORD) и DATABASE_URL.

### Миграция зависла

Остановите скрипт (Ctrl+C), проверьте логи:
```bash
docker logs myassistent_postgres
```

Возможно, нужно больше памяти контейнеру:
```yaml
# docker-compose.yml
services:
  postgres:
    mem_limit: 1g
```

---

**Последнее обновление:** 2025-10-10  
**Версия:** 0.9  
**Автор:** AI Assistant


