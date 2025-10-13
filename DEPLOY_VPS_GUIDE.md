# 🚀 ГАЙД ПО ДЕПЛОЮ НА VPS

**Сервер:** Ubuntu 22.04 (vm210211.vds.miran.ru)  
**IP:** 185.73.215.38  
**Дата:** 2025-10-13

---

## 📋 ЧТО У ТЕБЯ ЕСТЬ

### Информация о сервере:
```
Тарифный план: Base 6
Доменное имя: vm210211.vds.miran.ru
IP-адрес:     185.73.215.38
Пользователь: root
Пароль:       GK7gz9yGq15T
```

### Что это значит:
- ✅ Виртуальный сервер (VPS) на базе Ubuntu 22.04
- ✅ Полный root доступ (можешь делать что угодно)
- ✅ Внешний IP адрес (доступен из интернета)
- ✅ Можно поставить Docker, Python, всё что нужно

---

## 🔐 ШАГ 1: ПОДКЛЮЧЕНИЕ К СЕРВЕРУ

### Windows 10 → Установка SSH клиента

**Вариант 1: PowerShell (встроенный, рекомендую)**

1. Открой PowerShell (Win + X → Windows PowerShell)

2. Подключись к серверу:
```powershell
ssh root@185.73.215.38
```

3. При первом подключении увидишь:
```
The authenticity of host '185.73.215.38' can't be established.
Are you sure you want to continue connecting (yes/no)?
```
Напиши: `yes`

4. Введи пароль: `GK7gz9yGq15T`

5. Готово! Ты в сервере! 🎉

**Вариант 2: PuTTY (если PowerShell не работает)**

1. Скачай PuTTY: https://www.putty.org/
2. Запусти PuTTY
3. В поле "Host Name": `185.73.215.38`
4. Port: `22`
5. Connection type: `SSH`
6. Нажми "Open"
7. Login: `root`
8. Password: `GK7gz9yGq15T`

---

## 🛡️ ШАГ 2: БАЗОВАЯ БЕЗОПАСНОСТЬ (КРИТИЧНО!)

**Сразу после первого подключения!**

### 2.1. Смена пароля root

```bash
# Смени пароль root (обязательно!)
passwd

# Введи новый сложный пароль (запиши его!)
# Например: openssl rand -base64 32
```

### 2.2. Создание обычного пользователя

```bash
# Создать пользователя (вместо root)
adduser tradingbot

# Добавить в sudo группу
usermod -aG sudo tradingbot

# Переключиться на нового пользователя
su - tradingbot
```

**Дальше работай от пользователя `tradingbot`, не от root!**

### 2.3. Настройка SSH ключа (опционально, но безопаснее)

На твоем Windows компьютере (PowerShell):

```powershell
# Сгенерировать SSH ключ
ssh-keygen -t ed25519 -C "your_email@example.com"

# Нажми Enter 3 раза (путь по умолчанию, без passphrase)

# Скопировать ключ на сервер
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh tradingbot@185.73.215.38 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

Теперь можешь подключаться без пароля:
```powershell
ssh tradingbot@185.73.215.38
```

### 2.4. Настройка Firewall

```bash
# Разрешить только нужные порты
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 8000/tcp   # API
sudo ufw allow 5000/tcp   # MLflow
sudo ufw allow 3001/tcp   # Grafana
sudo ufw allow 9090/tcp   # Prometheus

# Включить firewall
sudo ufw enable

# Проверить статус
sudo ufw status
```

---

## 📦 ШАГ 3: УСТАНОВКА ЗАВИСИМОСТЕЙ

### 3.1. Обновление системы

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get autoremove -y
```

### 3.2. Установка Python 3.11

Ubuntu 22.04 идет с Python 3.10, но установим 3.11:

```bash
# Добавить PPA репозиторий
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt-get update

# Установить Python 3.11
sudo apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip
```

### 3.3. Установка Docker

```bash
# Установить Docker
sudo apt-get install -y \
    docker.io \
    docker-compose

# Запустить Docker
sudo systemctl start docker
sudo systemctl enable docker

# Добавить пользователя в группу docker
sudo usermod -aG docker $USER

# ВАЖНО: Перелогинься (exit и ssh снова)
exit
ssh tradingbot@185.73.215.38

# Проверить Docker
docker --version
docker-compose --version
```

### 3.4. Установка дополнительных утилит

```bash
sudo apt-get install -y \
    git \
    curl \
    htop \
    nano \
    postgresql-client
```

---

## 📂 ШАГ 4: КЛОНИРОВАНИЕ ПРОЕКТА

### 4.1. Настройка Git

```bash
# Настроить Git
git config --global user.name "Your Name"
git config --global user.email "your_email@example.com"
```

### 4.2. Клонирование репозитория

```bash
# Перейти в домашнюю папку
cd ~

# Клонировать проект
git clone https://github.com/straus97/myAssistent.git

# Перейти в проект
cd myAssistent
```

---

## 🔧 ШАГ 5: НАСТРОЙКА ПРОЕКТА

### 5.1. Создание .env файла

```bash
# Скопировать пример
cp server/.env.production .env

# Редактировать .env
nano .env
```

**Что нужно заменить в .env:**

```bash
# API_KEY - сгенерируй:
openssl rand -hex 32

# POSTGRES_PASSWORD - сгенерируй:
openssl rand -hex 32

# MLFLOW_PASSWORD - сгенерируй:
openssl rand -hex 16

# GRAFANA_PASSWORD - сгенерируй:
openssl rand -hex 16

# TELEGRAM_BOT_TOKEN - получи от @BotFather
# TELEGRAM_CHAT_ID - получи через @userinfobot
```

Сохранить: `Ctrl+X`, потом `Y`, потом `Enter`

### 5.2. Создание виртуального окружения

```bash
# Создать venv
python3.11 -m venv .venv

# Активировать venv
source .venv/bin/activate

# Обновить pip
pip install --upgrade pip

# Установить зависимости
pip install -r requirements.txt
```

Это займет 5-10 минут (много библиотек!)

---

## 🐳 ШАГ 6: ЗАПУСК DOCKER КОНТЕЙНЕРОВ

### 6.1. Запуск БД и сервисов

```bash
# Запустить PostgreSQL, MLflow, Prometheus, Grafana
docker-compose up -d

# Проверить что запустилось
docker ps

# Ждать 30 секунд для запуска PostgreSQL
sleep 30
```

### 6.2. Применение миграций БД

```bash
# Применить миграции
alembic upgrade head

# Проверить что БД создалась
psql postgresql://myassistent:ВАШ_POSTGRES_PASSWORD@localhost:5432/myassistent -c "\dt"
```

---

## 🚀 ШАГ 7: ЗАПУСК ПРИЛОЖЕНИЯ

### 7.1. Тестовый запуск (вручную)

```bash
# Активировать venv (если не активирован)
source .venv/bin/activate

# Запустить API
uvicorn src.main:app --host 0.0.0.0 --port 8000

# Открой в браузере:
# http://185.73.215.38:8000/docs
```

Если всё работает - жми `Ctrl+C` для остановки.

### 7.2. Автозапуск через systemd

```bash
# Создать systemd service
sudo nano /etc/systemd/system/myassistent.service
```

Вставь (замени `/home/tradingbot` на свой путь):

```ini
[Unit]
Description=MyAssistent Trading Bot
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=tradingbot
WorkingDirectory=/home/tradingbot/myAssistent
Environment="PATH=/home/tradingbot/myAssistent/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/tradingbot/myAssistent/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Сохранить и включить:

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable myassistent

# Запустить сервис
sudo systemctl start myassistent

# Проверить статус
sudo systemctl status myassistent

# Смотреть логи в реальном времени
sudo journalctl -u myassistent -f
```

---

## 🔄 ШАГ 8: АВТОМАТИЗАЦИЯ ОБНОВЛЕНИЙ

### 8.1. Скрипт обновления (уже создан)

```bash
# Сделать скрипт исполняемым
chmod +x server/deploy.sh

# Использование:

# Полный deploy (первый раз)
./server/deploy.sh full

# Обновление кода (git pull + restart)
./server/deploy.sh update
```

### 8.2. Webhook для автоматического деплоя (опционально)

Создай скрипт для webhook:

```bash
nano ~/webhook_deploy.sh
```

Вставь:

```bash
#!/bin/bash
cd /home/tradingbot/myAssistent
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt --upgrade
alembic upgrade head
sudo systemctl restart myassistent
```

Сделать исполняемым:

```bash
chmod +x ~/webhook_deploy.sh
```

Настроить GitHub webhook:
1. Репозиторий → Settings → Webhooks → Add webhook
2. Payload URL: `http://185.73.215.38:9000/webhook`
3. Content type: `application/json`
4. Secret: (сгенерируй любой)

---

## 📊 ШАГ 9: ДОСТУП К СЕРВИСАМ

После запуска доступны:

```
API (Swagger):    http://185.73.215.38:8000/docs
MLflow:           http://185.73.215.38:5000
Prometheus:       http://185.73.215.38:9090
Grafana:          http://185.73.215.38:3001

Логины/пароли указаны в .env файле
```

---

## 🔍 ШАГ 10: МОНИТОРИНГ И ОТЛАДКА

### 10.1. Полезные команды

```bash
# Статус сервиса
sudo systemctl status myassistent

# Логи сервиса
sudo journalctl -u myassistent -f

# Логи приложения
tail -f ~/myAssistent/logs/app.log

# Статус Docker контейнеров
docker ps

# Логи PostgreSQL
docker logs myassistent_postgres

# Использование ресурсов
htop
```

### 10.2. Проверка что всё работает

```bash
# API health check
curl http://localhost:8000/health

# Проверка БД
docker exec myassistent_postgres psql -U myassistent -c "SELECT 1"

# Проверка MLflow
curl http://localhost:5000
```

---

## 🔒 ШАГ 11: БЕЗОПАСНОСТЬ (ПРОВЕРКА)

### 11.1. Что проверить:

```bash
# ✅ .env файл НЕ в Git
cat .gitignore | grep .env

# ✅ Файлы с секретами НЕ в репо
git status --ignored

# ✅ Firewall включен
sudo ufw status

# ✅ Сильные пароли в .env
cat .env
```

### 11.2. Что НЕ ДОЛЖНО быть в Git:

- ❌ `.env` файл
- ❌ Пароли БД
- ❌ API ключи
- ❌ Telegram токены
- ❌ Файлы `*.db`
- ❌ Логи `logs/`
- ❌ Модели `*.pkl`

---

## 📝 ШАГ 12: РАБОЧИЙ ПРОЦЕСС

### На Windows (разработка):

```powershell
# 1. Редактируешь код в VS Code
# 2. Тестируешь локально
python -m uvicorn src.main:app --reload

# 3. Коммитишь изменения
git add .
git commit -m "feat: новая функция"
git push origin main
```

### На сервере (автоматическое обновление):

```bash
# Подключиться к серверу
ssh tradingbot@185.73.215.38

# Перейти в проект
cd ~/myAssistent

# Обновить код и перезапустить
./server/deploy.sh update
```

**Всё! Обновление за 30 секунд!** 🚀

---

## 🆘 TROUBLESHOOTING

### Проблема: Не могу подключиться к серверу

```bash
# Проверь что сервер доступен
ping 185.73.215.38

# Проверь SSH порт
telnet 185.73.215.38 22
```

### Проблема: API не запускается

```bash
# Смотри логи
sudo journalctl -u myassistent -f

# Проверь .env файл
cat .env

# Проверь порт 8000
sudo netstat -tulpn | grep 8000
```

### Проблема: Docker контейнеры не запускаются

```bash
# Проверить Docker
sudo systemctl status docker

# Перезапустить Docker
sudo systemctl restart docker

# Запустить контейнеры заново
docker-compose up -d

# Смотреть логи
docker logs myassistent_postgres
```

### Проблема: Permission denied

```bash
# Проверить владельца файлов
ls -la ~/myAssistent

# Исправить права
sudo chown -R tradingbot:tradingbot ~/myAssistent
chmod +x server/deploy.sh
```

---

## 📚 ПОЛЕЗНЫЕ РЕСУРСЫ

### Документация:

- SSH: https://www.ssh.com/academy/ssh/command
- Docker: https://docs.docker.com/
- systemd: https://www.freedesktop.org/software/systemd/man/
- UFW: https://help.ubuntu.com/community/UFW

### Команды для копирования файлов:

```powershell
# Windows → Сервер
scp C:\path\to\file.txt tradingbot@185.73.215.38:~/myAssistent/

# Сервер → Windows
scp tradingbot@185.73.215.38:~/myAssistent/file.txt C:\path\to\
```

---

## ✅ ЧЕКЛИСТ ДЕПЛОЯ

- [ ] Подключился к серверу через SSH
- [ ] Сменил root пароль
- [ ] Создал пользователя tradingbot
- [ ] Настроил firewall (ufw)
- [ ] Установил Python 3.11
- [ ] Установил Docker
- [ ] Клонировал репозиторий
- [ ] Создал .env файл (со сгенерированными паролями)
- [ ] Установил Python зависимости
- [ ] Запустил Docker контейнеры
- [ ] Применил миграции БД
- [ ] Создал systemd service
- [ ] Запустил приложение
- [ ] Проверил доступ к API
- [ ] Настроил автоматическое обновление

---

## 🎉 ГОТОВО!

**Твой бот теперь работает на VPS 24/7!**

**Доступ:**
- API: http://185.73.215.38:8000/docs
- MLflow: http://185.73.215.38:5000
- Grafana: http://185.73.215.38:3001

**Обновление:**
```bash
ssh tradingbot@185.73.215.38
cd myAssistent
./server/deploy.sh update
```

**Удачи! 🚀💰**

