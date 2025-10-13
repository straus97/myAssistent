# 🖥️ Linux Сервер для Крипто-Трейдинг Бота

**Дата:** 2025-10-13  
**Цель:** Выбор оптимального сервера для 24/7 работы торгового бота

---

## 🎯 ТРЕБОВАНИЯ К СЕРВЕРУ

### Минимальные (для старта):
- **CPU:** 2 vCPU (Intel/AMD)
- **RAM:** 4 GB
- **Диск:** 40 GB SSD
- **Сеть:** 100 Mbps (безлимитный трафик)
- **Uptime:** 99.9%+

### Рекомендуемые (оптимально):
- **CPU:** 4 vCPU (Intel Xeon / AMD EPYC)
- **RAM:** 8 GB
- **Диск:** 80 GB NVMe SSD
- **Сеть:** 1 Gbps (безлимитный трафик)
- **Uptime:** 99.99%+

### Для будущего ML/RL (если понадобится):
- **CPU:** 8+ vCPU
- **RAM:** 16+ GB
- **GPU:** NVIDIA Tesla T4 / V100 (опционально)
- **Диск:** 160+ GB NVMe SSD

---

## 🏆 ТОП-5 РЕКОМЕНДУЕМЫХ ПРОВАЙДЕРОВ

### 1. **Timeweb Cloud** (Россия) 🥇
**Почему лучший для РФ:**
- ✅ Российская локация (Москва, СПб)
- ✅ Оплата рублями (карта РФ)
- ✅ Техподдержка 24/7 на русском
- ✅ Отличная цена/качество
- ✅ Простая панель управления

**Тариф "Cloud Server S":**
- CPU: 2 vCPU
- RAM: 4 GB
- Диск: 40 GB SSD
- Цена: **~500₽/месяц**
- Uptime: 99.9%

**Тариф "Cloud Server M" (рекомендую):**
- CPU: 4 vCPU
- RAM: 8 GB
- Диск: 80 GB SSD
- Цена: **~1000₽/месяц**
- Uptime: 99.95%

**Ссылка:** https://timeweb.cloud/

---

### 2. **VDSina.ru** (Россия) 🥈
**Почему хорош:**
- ✅ Недорогие тарифы
- ✅ Российская локация
- ✅ Оплата рублями
- ✅ Гибкая конфигурация

**Тариф "VPS-4":**
- CPU: 4 vCPU
- RAM: 8 GB
- Диск: 80 GB NVMe
- Цена: **~800₽/месяц**

**Ссылка:** https://vdsina.ru/

---

### 3. **DigitalOcean** (США/Европа) 🥉
**Почему хорош:**
- ✅ Надежность и стабильность
- ✅ Отличная документация
- ✅ Snapshots и backups
- ⚠️ Оплата $ картой (может быть проблема)

**Тариф "Basic Droplet":**
- CPU: 2 vCPU
- RAM: 4 GB
- Диск: 80 GB SSD
- Цена: **$24/месяц (~2300₽)**

**Тариф "Premium Intel" (рекомендую):**
- CPU: 4 vCPU Intel
- RAM: 8 GB
- Диск: 160 GB NVMe
- Цена: **$48/месяц (~4600₽)**

**Ссылка:** https://www.digitalocean.com/

---

### 4. **Selectel** (Россия/Европа)
**Почему хорош:**
- ✅ Крупный провайдер
- ✅ Российская и европейская локация
- ✅ Оплата рублями
- ⚠️ Дороже конкурентов

**Тариф "Cloud Server":**
- CPU: 4 vCPU
- RAM: 8 GB
- Диск: 80 GB SSD
- Цена: **~1500₽/месяц**

**Ссылка:** https://selectel.ru/

---

### 5. **Hetzner** (Германия/Финляндия)
**Почему хорош:**
- ✅ Отличная цена/качество
- ✅ Мощное железо
- ⚠️ Оплата € картой (может быть проблема)
- ⚠️ Европейская локация (латенси ~50-100ms)

**Тариф "CX32" (рекомендую):**
- CPU: 4 vCPU AMD
- RAM: 8 GB
- Диск: 80 GB NVMe
- Цена: **€8.46/месяц (~850₽)**

**Ссылка:** https://www.hetzner.com/cloud

---

## 📊 СРАВНИТЕЛЬНАЯ ТАБЛИЦА

| Провайдер | CPU | RAM | Диск | Цена/мес | Локация | Оплата РФ |
|-----------|-----|-----|------|----------|---------|-----------|
| **Timeweb Cloud M** | 4 vCPU | 8 GB | 80 GB SSD | **~1000₽** | 🇷🇺 Москва | ✅ Да |
| **VDSina VPS-4** | 4 vCPU | 8 GB | 80 GB NVMe | **~800₽** | 🇷🇺 Москва | ✅ Да |
| **DigitalOcean** | 4 vCPU | 8 GB | 160 GB NVMe | ~4600₽ | 🇺🇸 США | ⚠️ Сложно |
| **Selectel** | 4 vCPU | 8 GB | 80 GB SSD | ~1500₽ | 🇷🇺 Москва | ✅ Да |
| **Hetzner CX32** | 4 vCPU | 8 GB | 80 GB NVMe | **~850₽** | 🇩🇪 Германия | ⚠️ Сложно |

---

## 🎯 МОЯ РЕКОМЕНДАЦИЯ

### **Вариант 1: Для начала (бюджетный)**
**Timeweb Cloud Server S**
- Цена: **500₽/месяц**
- 2 vCPU / 4 GB RAM / 40 GB SSD
- Отлично для EMA Crossover (простая стратегия)
- Легко апгрейдить при необходимости

### **Вариант 2: Оптимальный (рекомендую!) 🏆**
**Timeweb Cloud Server M** или **VDSina VPS-4**
- Цена: **800-1000₽/месяц**
- 4 vCPU / 8 GB RAM / 80 GB SSD
- Запас мощности для ML/RL в будущем
- Запустишь Docker + PostgreSQL + MLflow + Grafana

### **Вариант 3: Если проблем с оплатой нет**
**Hetzner CX32**
- Цена: **~850₽/месяц** (€8.46)
- Лучшее железо за эти деньги
- Но европейская локация (латенси +50ms)

---

## 🐧 ВЫБОР ОС (ОПЕРАЦИОННОЙ СИСТЕМЫ)

### **Рекомендую: Ubuntu 22.04 LTS** ✅

**Почему именно Ubuntu 22.04 LTS:**
- ✅ Долгосрочная поддержка (до 2027 года)
- ✅ Огромное комьюнити (легко найти решения)
- ✅ Совместимость со всеми инструментами
- ✅ Простая установка Docker
- ✅ Стабильность и безопасность
- ✅ Официальная поддержка Python 3.10+

**Альтернативы (если опыт с Linux):**
- **Debian 12** - еще стабильнее, но менее свежие пакеты
- **Rocky Linux 9** - аналог CentOS, для энтерпрайза
- **Ubuntu 24.04 LTS** - самая свежая LTS (вышла в 2024)

**НЕ рекомендую:**
- ❌ Arch Linux - слишком нестабильно для продакшн
- ❌ Fedora - короткий цикл поддержки
- ❌ openSUSE - меньше документации

---

## 🔧 ЧТО УСТАНОВИМ НА СЕРВЕРЕ

### **Базовые компоненты:**
```bash
# 1. Обновление системы
sudo apt update && sudo apt upgrade -y

# 2. Python 3.11 (наш проект на нем)
sudo apt install python3.11 python3.11-venv python3-pip -y

# 3. Git
sudo apt install git -y

# 4. Docker + Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo apt install docker-compose-plugin -y

# 5. Nginx (reverse proxy)
sudo apt install nginx -y

# 6. UFW (firewall)
sudo apt install ufw -y
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
sudo ufw enable

# 7. Fail2ban (защита от брутфорса)
sudo apt install fail2ban -y

# 8. Мониторинг (htop, ncdu)
sudo apt install htop ncdu -y
```

### **Docker контейнеры (опционально):**
- PostgreSQL 16 (вместо SQLite)
- MLflow (отслеживание экспериментов)
- Prometheus + Grafana (мониторинг)
- Redis (кэширование)

---

## 📦 ПОДГОТОВКА СЕРВЕРА (ПОШАГОВО)

### **Шаг 1: Заказ сервера**
1. Зарегистрироваться на **Timeweb.cloud** (или VDSina)
2. Выбрать тариф **Cloud Server M** (4 vCPU / 8 GB)
3. ОС: **Ubuntu 22.04 LTS**
4. Локация: **Москва** (минимальная латенси)
5. SSH-ключ: создать или использовать существующий
6. Оплатить (от 1000₽/месяц)

### **Шаг 2: Первый вход по SSH**
```bash
# С Windows (PowerShell)
ssh root@YOUR_SERVER_IP

# Первый вход: обновить систему
sudo apt update && sudo apt upgrade -y

# Создать пользователя (не работать под root!)
adduser trader
usermod -aG sudo trader
su - trader
```

### **Шаг 3: Установка базовых компонентов**
```bash
# Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip git -y

# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Проверка
python3.11 --version
docker --version
git --version
```

### **Шаг 4: Клонирование проекта**
```bash
cd ~
git clone https://github.com/straus97/myAssistent.git
cd myAssistent

# Создание venv
python3.11 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install --upgrade pip
pip install -r requirements.txt
```

### **Шаг 5: Настройка .env**
```bash
# Копировать .env
cp env.example.txt .env
nano .env

# Заполнить:
# - API_KEY (новый, длинный!)
# - TELEGRAM_BOT_TOKEN
# - TELEGRAM_CHAT_ID
# - BYBIT_API_KEY / BYBIT_SECRET (для real trading)
```

### **Шаг 6: Первый запуск**
```bash
# Тестовый запуск
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# Проверить с локального компьютера:
# http://YOUR_SERVER_IP:8000/docs

# Остановить: Ctrl+C
```

### **Шаг 7: Systemd сервис (автозапуск)**
```bash
sudo nano /etc/systemd/system/trading-bot.service
```

Содержимое файла:
```ini
[Unit]
Description=Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/myAssistent
Environment="PATH=/home/trader/myAssistent/venv/bin"
ExecStart=/home/trader/myAssistent/venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# Проверка статуса
sudo systemctl status trading-bot

# Логи
sudo journalctl -u trading-bot -f
```

### **Шаг 8: Nginx reverse proxy (опционально)**
Если хочешь доступ через доменное имя:
```bash
sudo nano /etc/nginx/sites-available/trading-bot
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/trading-bot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔐 БЕЗОПАСНОСТЬ

### **Обязательно:**
1. ✅ **SSH ключи** (отключить пароли)
   ```bash
   sudo nano /etc/ssh/sshd_config
   # PasswordAuthentication no
   sudo systemctl restart sshd
   ```

2. ✅ **UFW Firewall**
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

3. ✅ **Fail2ban** (защита от брутфорса)
   ```bash
   sudo apt install fail2ban -y
   sudo systemctl enable fail2ban
   ```

4. ✅ **Автоматические обновления**
   ```bash
   sudo apt install unattended-upgrades -y
   sudo dpkg-reconfigure --priority=low unattended-upgrades
   ```

5. ✅ **Backup БД** (ежедневно)
   ```bash
   # Cron задача для бэкапа
   crontab -e
   # Добавить:
   0 3 * * * cp ~/myAssistent/assistant.db ~/backups/assistant_$(date +\%Y\%m\%d).db
   ```

---

## 💰 СТОИМОСТЬ (ИТОГО)

### **Минимальная конфигурация:**
- Сервер (Timeweb S): **500₽/месяц**
- Домен (опционально): **200₽/год** (~17₽/месяц)
- **Итого: ~520₽/месяц**

### **Рекомендуемая конфигурация:**
- Сервер (Timeweb M): **1000₽/месяц**
- Домен (опционально): **200₽/год** (~17₽/месяц)
- Backup storage (опционально): **100₽/месяц**
- **Итого: ~1120₽/месяц**

### **С запасом на будущее:**
- Сервер (Timeweb L): **2000₽/месяц** (8 vCPU / 16 GB)
- Домен: **200₽/год**
- Backup storage: **200₽/месяц**
- **Итого: ~2220₽/месяц**

---

## 📋 ЧЕКЛИСТ ПЕРЕД ЗАПУСКОМ

- [ ] Выбрать провайдера (рекомендую Timeweb M)
- [ ] Заказать сервер (Ubuntu 22.04 LTS)
- [ ] Настроить SSH доступ
- [ ] Обновить систему
- [ ] Установить Python 3.11, Docker, Git
- [ ] Клонировать проект с GitHub
- [ ] Создать venv и установить зависимости
- [ ] Настроить .env (API ключи)
- [ ] Создать systemd сервис
- [ ] Настроить UFW firewall
- [ ] Установить fail2ban
- [ ] Настроить автоматические backup
- [ ] Протестировать API через /docs
- [ ] Запустить Paper Trading Monitor
- [ ] Настроить мониторинг (опционально)

---

## 🎓 ПОЛЕЗНЫЕ ССЫЛКИ

- **Ubuntu Server Guide:** https://ubuntu.com/server/docs
- **Docker Documentation:** https://docs.docker.com/
- **DigitalOcean Tutorials:** https://www.digitalocean.com/community/tutorials
- **UFW Guide:** https://ubuntu.com/server/docs/security-firewall
- **Systemd Services:** https://www.freedesktop.org/software/systemd/man/systemd.service.html

---

## ❓ FAQ

**Q: Сколько будет потреблять трафика?**  
A: ~1-2 GB/месяц (API запросы к биржам + новости)

**Q: Нужен ли GPU для EMA Crossover?**  
A: Нет! GPU нужен только для ML/RL обучения.

**Q: Можно ли запустить несколько ботов на одном сервере?**  
A: Да! Тариф M (4 vCPU / 8 GB) потянет 3-5 ботов.

**Q: Что делать если сервер упал?**  
A: Systemd автоматически перезапустит. Telegram уведомления придут.

**Q: Как обновить код бота?**  
A: `git pull && sudo systemctl restart trading-bot`

**Q: Нужен ли domain для работы?**  
A: Нет, можно работать по IP. Но удобнее с доменом.

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ

1. **Сегодня:**
   - Выбрать провайдера (Timeweb / VDSina / Hetzner)
   - Зарегистрироваться и заказать сервер
   - Первый вход по SSH

2. **Завтра:**
   - Установить базовые компоненты
   - Клонировать проект
   - Первый запуск

3. **Через 2-3 дня:**
   - Настроить systemd сервис
   - Запустить Paper Trading 24/7
   - Мониторить результаты

4. **Через неделю:**
   - Анализ Paper Trading результатов
   - Решение о переходе на real trading

---

**ГОТОВ К ВЫБОРУ! 🎉**

**Мой топ выбор:** Timeweb Cloud Server M (1000₽/мес) или VDSina VPS-4 (800₽/мес)

