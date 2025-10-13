# ⚡ БЫСТРЫЙ СТАРТ: ДЕПЛОЙ ЗА 10 МИНУТ

**Для тех кто хочет быстро!**

---

## 🔐 1. ПОДКЛЮЧЕНИЕ К СЕРВЕРУ (1 минута)

**Windows PowerShell:**

```powershell
ssh root@185.73.215.38
# Пароль: GK7gz9yGq15T
```

---

## 🛡️ 2. БАЗОВАЯ БЕЗОПАСНОСТЬ (2 минуты)

```bash
# Смени root пароль
passwd

# Создай пользователя
adduser tradingbot
usermod -aG sudo tradingbot

# Переключись на него
su - tradingbot
```

---

## 📦 3. УСТАНОВКА ЗАВИСИМОСТЕЙ (3 минуты)

```bash
# Обнови систему
sudo apt-get update && sudo apt-get upgrade -y

# Установи всё нужное
sudo apt-get install -y \
    python3.11 python3.11-venv python3-pip \
    docker.io docker-compose \
    git curl htop

# Добавь себя в docker группу
sudo usermod -aG docker $USER

# ВАЖНО: Перелогинься!
exit
ssh tradingbot@185.73.215.38
```

---

## 📂 4. КЛОНИРОВАНИЕ ПРОЕКТА (1 минута)

```bash
cd ~
git clone https://github.com/straus97/myAssistent.git
cd myAssistent
```

---

## 🔧 5. НАСТРОЙКА (2 минуты)

```bash
# Создай .env
cp .env.production.example .env

# Сгенерируй пароли
echo "API_KEY=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -hex 32)"
echo "MLFLOW_PASSWORD=$(openssl rand -hex 16)"
echo "GRAFANA_PASSWORD=$(openssl rand -hex 16)"

# Отредактируй .env (вставь пароли)
nano .env
# Ctrl+X → Y → Enter для сохранения
```

---

## 🚀 6. АВТОМАТИЧЕСКИЙ DEPLOY (1 минута)

```bash
# Сделай скрипт исполняемым
chmod +x server/deploy.sh

# Запусти полный deploy
./server/deploy.sh full
```

Скрипт сделает всё сам:
- Установит Python зависимости
- Запустит Docker контейнеры
- Применит миграции БД
- Создаст systemd service
- Запустит приложение

---

## ✅ 7. ПРОВЕРКА (10 секунд)

```bash
# Статус
sudo systemctl status myassistent

# Открой в браузере
# http://185.73.215.38:8000/docs
```

---

## 🔄 8. ОБНОВЛЕНИЕ КОДА (30 секунд)

**На Windows:**
```powershell
git add .
git commit -m "feat: изменения"
git push
```

**На сервере:**
```bash
ssh tradingbot@185.73.215.38
cd myAssistent
./server/deploy.sh update
```

**ГОТОВО!** 🎉

---

## 📊 ДОСТУП К СЕРВИСАМ

```
API:        http://185.73.215.38:8000/docs
MLflow:     http://185.73.215.38:5000
Grafana:    http://185.73.215.38:3001
Prometheus: http://185.73.215.38:9090
```

---

## 🆘 ПРОБЛЕМЫ?

Смотри полный гайд: `DEPLOY_VPS_GUIDE.md`

