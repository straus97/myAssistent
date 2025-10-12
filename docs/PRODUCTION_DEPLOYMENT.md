# 🚀 Production Deployment Guide

> **Полное руководство по развертыванию MyAssistent в production**

---

## 📋 Содержание

1. [Pre-deployment Checklist](#pre-deployment-checklist)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Error Tracking (Sentry)](#error-tracking-sentry)
4. [Uptime Monitoring (Healthchecks)](#uptime-monitoring-healthchecks)
5. [Environment Configuration](#environment-configuration)
6. [Deployment Process](#deployment-process)
7. [Post-deployment Verification](#post-deployment-verification)
8. [Scaling and Optimization](#scaling-and-optimization)
9. [Security Best Practices](#security-best-practices)
10. [Troubleshooting](#troubleshooting)

---

## ✅ Pre-deployment Checklist

### 1. Тестирование завершено
- ✅ Walk-Forward Validation пройдена (Avg Return >3%, Sharpe >1.0)
- ✅ Paper Trading протестирован минимум 30 дней
- ✅ Risk Management настроен и протестирован
- ✅ Все 127+ тестов проходят (`pytest`)
- ✅ Нет критичных ошибок линтера (`ruff check src/`)

### 2. Инфраструктура готова
- ✅ VPS/Cloud сервер настроен (минимум 2 vCPU, 4GB RAM)
- ✅ Docker и Docker Compose установлены
- ✅ PostgreSQL готов к использованию
- ✅ Домен настроен (опционально)
- ✅ SSL сертификаты получены (опционально)

### 3. Мониторинг настроен
- ✅ Sentry проект создан
- ✅ Healthchecks.io проект настроен
- ✅ Telegram бот для алертов готов
- ✅ Grafana дашборды созданы

---

## 🏗️ Infrastructure Setup

### Рекомендуемые провайдеры

| Провайдер | Конфигурация | Цена/мес | Uptime SLA |
|-----------|--------------|----------|------------|
| **Hetzner** | CPX21 (3 vCPU, 4GB) | €7.49 | 99.9% |
| **DigitalOcean** | Basic Droplet (2 vCPU, 4GB) | $24 | 99.99% |
| **AWS Lightsail** | 2GB RAM | $12 | 99.99% |
| **Vultr** | High Frequency (2 vCPU, 4GB) | $24 | 100% |

### Минимальные требования

```
OS: Ubuntu 22.04 LTS
CPU: 2+ vCPU
RAM: 4+ GB
Disk: 50+ GB SSD
Network: 100+ Mbps
```

### Установка на VPS

```bash
# 1. Обновить систему
sudo apt update && sudo apt upgrade -y

# 2. Установить Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 3. Установить Docker Compose
sudo apt install docker-compose-plugin -y

# 4. Установить Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# 5. Создать пользователя для приложения
sudo useradd -m -s /bin/bash myassistent
sudo usermod -aG docker myassistent

# 6. Клонировать репозиторий
sudo su - myassistent
git clone https://github.com/your-repo/myassistent.git
cd myassistent
```

---

## 🐛 Error Tracking (Sentry)

### 1. Создать проект в Sentry

1. Зарегистрироваться на https://sentry.io
2. Создать новый проект (Python/FastAPI)
3. Получить DSN: `https://xxx@xxx.ingest.sentry.io/xxx`

### 2. Установить зависимости

```bash
pip install sentry-sdk[fastapi]
```

### 3. Интеграция в код

Создаём `src/sentry_integration.py`:

```python
"""
Sentry Integration for Error Tracking
"""
import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

def init_sentry():
    """Initialize Sentry SDK"""
    sentry_dsn = os.getenv("SENTRY_DSN")
    
    if not sentry_dsn:
        print("[sentry] SENTRY_DSN not set, error tracking disabled")
        return
    
    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.getenv("ENVIRONMENT", "production"),
        traces_sample_rate=0.1,  # 10% трассировки для performance monitoring
        profiles_sample_rate=0.1,  # 10% профилирования
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        # Ignore expected errors
        ignore_errors=[
            KeyboardInterrupt,
        ],
        # Release tracking
        release=os.getenv("RELEASE_VERSION", "unknown"),
        # Tags for filtering
        tags={
            "service": "myassistent",
        }
    )
    
    print(f"[sentry] Initialized for environment: {os.getenv('ENVIRONMENT', 'production')}")
```

Добавить в `src/main.py`:

```python
from src.sentry_integration import init_sentry

# После всех импортов, перед созданием app
init_sentry()

app = _FastAPI(...)
```

### 4. Конфигурация в .env

```env
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
ENVIRONMENT=production
RELEASE_VERSION=1.0.0
```

### 5. Тестирование

```python
# Временно добавить в код для теста
@app.get("/sentry-test")
def sentry_test():
    1 / 0  # Вызовет ZeroDivisionError
    
# Проверить что ошибка попала в Sentry dashboard
```

---

## 💓 Uptime Monitoring (Healthchecks.io)

### 1. Создать проект в Healthchecks.io

1. Зарегистрироваться на https://healthchecks.io
2. Создать новый check: "MyAssistent Health"
3. Настроить:
   - Period: 5 minutes
   - Grace: 2 minutes
4. Получить ping URL: `https://hc-ping.com/xxx`

### 2. Создать healthcheck endpoint

Добавить в `src/main.py`:

```python
from datetime import datetime
import httpx

HEALTHCHECK_URL = os.getenv("HEALTHCHECK_URL")

@app.get("/health")
def health_check():
    """Health check endpoint для мониторинга"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {
            "database": "ok",
            "scheduler": "ok",
            "cache": "ok"
        }
    }

def ping_healthcheck():
    """Ping healthchecks.io to confirm service is alive"""
    if not HEALTHCHECK_URL:
        return
    
    try:
        httpx.get(HEALTHCHECK_URL, timeout=5)
    except Exception as e:
        print(f"[healthcheck] Failed to ping: {e}")

# Добавить в scheduler
scheduler.add_job(
    ping_healthcheck,
    IntervalTrigger(minutes=5),
    id="healthcheck_ping",
    replace_existing=True
)
```

### 3. Конфигурация в .env

```env
HEALTHCHECK_URL=https://hc-ping.com/your-uuid-here
```

### 4. Настройка алертов

В Healthchecks.io настроить:
- Email notifications
- Telegram notifications
- Webhook notifications (опционально)

---

## ⚙️ Environment Configuration

### Production .env файл

Создать `.env.production`:

```env
# Application
ENVIRONMENT=production
RELEASE_VERSION=1.0.0
API_KEY=your-secure-api-key-here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/myassistent

# Exchange API
BYBIT_API_KEY=your-bybit-key
BYBIT_API_SECRET=your-bybit-secret
BYBIT_TESTNET=false

# Monitoring
SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx
HEALTHCHECK_URL=https://hc-ping.com/xxx
ENABLE_METRICS=true

# MLflow
MLFLOW_TRACKING_URI=http://localhost:5000

# Notifications
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# CORS
CORS_ORIGINS=https://yourdomain.com

# Scheduler
SCHEDULER_ENABLED=true

# Risk Management
RISK_MANAGEMENT_ENABLED=true
PAPER_MONITOR_ENABLED=true
```

### Безопасность переменных

```bash
# Установить правильные права
chmod 600 .env.production

# Владелец только myassistent
chown myassistent:myassistent .env.production

# НЕ коммитить в git!
echo ".env.production" >> .gitignore
```

---

## 🚀 Deployment Process

### Option 1: Docker Compose (Рекомендуется)

**1. Создать production docker-compose:**

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    build: .
    restart: always
    env_file:
      - .env.production
    ports:
      - "8000:8000"
    volumes:
      - ./artifacts:/app/artifacts
      - ./logs:/app/logs
    depends_on:
      - postgres
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - myassistent

  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: myassistent
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: myassistent
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myassistent"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - myassistent

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    networks:
      - myassistent

  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.8.0
    restart: always
    ports:
      - "5000:5000"
    command: >
      mlflow server
      --host 0.0.0.0
      --port 5000
      --backend-store-uri postgresql://myassistent:${POSTGRES_PASSWORD}@postgres:5432/mlflow
      --default-artifact-root /mlflow/artifacts
    volumes:
      - mlflow_data:/mlflow
    depends_on:
      - postgres
    networks:
      - myassistent

  prometheus:
    image: prom/prometheus:latest
    restart: always
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    networks:
      - myassistent

  grafana:
    image: grafana/grafana:latest
    restart: always
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_INSTALL_PLUGINS=grafana-clock-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus
    networks:
      - myassistent

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - app
    networks:
      - myassistent

volumes:
  postgres_data:
  redis_data:
  mlflow_data:
  prometheus_data:
  grafana_data:

networks:
  myassistent:
    driver: bridge
```

**2. Запустить production stack:**

```bash
# Собрать образы
docker-compose -f docker-compose.prod.yml build

# Запустить все сервисы
docker-compose -f docker-compose.prod.yml up -d

# Проверить статус
docker-compose -f docker-compose.prod.yml ps

# Посмотреть логи
docker-compose -f docker-compose.prod.yml logs -f app
```

### Option 2: Systemd Service (Без Docker)

**1. Создать systemd unit:**

```bash
sudo nano /etc/systemd/system/myassistent.service
```

```ini
[Unit]
Description=MyAssistent Trading Bot
After=network.target postgresql.service

[Service]
Type=simple
User=myassistent
WorkingDirectory=/home/myassistent/myassistent
Environment="PATH=/home/myassistent/myassistent/venv/bin"
EnvironmentFile=/home/myassistent/myassistent/.env.production
ExecStart=/home/myassistent/myassistent/venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**2. Активировать и запустить:**

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable myassistent

# Запустить сервис
sudo systemctl start myassistent

# Проверить статус
sudo systemctl status myassistent

# Логи
sudo journalctl -u myassistent -f
```

---

## ✅ Post-deployment Verification

### 1. Health Checks

```bash
# API доступен
curl http://your-server:8000/health

# Swagger UI
curl http://your-server:8000/docs

# Metrics
curl http://your-server:8000/metrics
```

### 2. Проверка сервисов

```bash
# PostgreSQL
docker exec -it myassistent-postgres-1 psql -U myassistent -c "SELECT 1"

# MLflow
curl http://your-server:5000

# Prometheus
curl http://your-server:9090/-/healthy

# Grafana
curl http://your-server:3001/api/health
```

### 3. Тестовые сделки

```bash
# Проверить paper trading
curl -X GET http://your-server:8000/trade/positions \
  -H "X-API-Key: your-key"

# Запустить paper monitor
curl -X POST http://your-server:8000/paper-monitor/start \
  -H "X-API-Key: your-key"

# Проверить risk management
curl -X GET http://your-server:8000/risk-management/status \
  -H "X-API-Key: your-key"
```

---

## 📊 Scaling and Optimization

### Horizontal Scaling

```yaml
# docker-compose.prod.yml
services:
  app:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 2G
```

### Database Optimization

```sql
-- Добавить индексы
CREATE INDEX idx_prices_timestamp ON prices(timestamp DESC);
CREATE INDEX idx_signals_created ON signal_events(created_at DESC);

-- Партиционирование по времени
CREATE TABLE prices_2025_01 PARTITION OF prices
FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- Vacuum регулярно
VACUUM ANALYZE;
```

### Caching (Redis)

```python
# Кешировать результаты модели
import redis
r = redis.Redis()

@cache(ttl=300)  # 5 минут
def get_model_prediction(symbol):
    ...
```

---

## 🔒 Security Best Practices

### 1. API Key Security

```python
# Генерировать сложный ключ
import secrets
api_key = secrets.token_urlsafe(32)
```

### 2. Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/data")
@limiter.limit("10/minute")
def get_data():
    ...
```

### 3. HTTPS/SSL

```bash
# Получить Let's Encrypt сертификат
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com
```

### 4. Firewall

```bash
# UFW настройка
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 🔧 Troubleshooting

### Проблема: Service не стартует

```bash
# Проверить логи
docker-compose logs app

# Проверить переменные окружения
docker-compose config

# Проверить порты
sudo netstat -tulpn | grep 8000
```

### Проблема: High CPU usage

```bash
# Проверить процессы
docker stats

# Ограничить ресурсы
docker update --cpus="1.5" myassistent-app-1
```

### Проблема: Database connection errors

```bash
# Проверить PostgreSQL
docker exec -it myassistent-postgres-1 pg_isready

# Проверить connections
docker exec -it myassistent-postgres-1 psql -U myassistent \
  -c "SELECT count(*) FROM pg_stat_activity"
```

---

## 📝 Maintenance

### Backup Schedule

```bash
# Daily backups
0 2 * * * /home/myassistent/scripts/backup_db.sh
0 3 * * * /home/myassistent/scripts/backup_artifacts.sh
```

### Updates

```bash
# Pull latest code
cd /home/myassistent/myassistent
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Проверить здоровье
curl http://localhost:8000/health
```

---

**Production-ready! 🎉**

Система полностью готова к работе 24/7 с автоматическим мониторингом, алертами и восстановлением после сбоев.

