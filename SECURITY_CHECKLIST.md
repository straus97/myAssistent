# 🔒 ЧЕКЛИСТ БЕЗОПАСНОСТИ

**Проверь ПЕРЕД деплоем на сервер!**

---

## ✅ ЧТО ПРОВЕРЕНО

### 1. Секреты НЕ в Git ✅

**Проверка:**
```bash
git status --ignored | grep .env
cat .gitignore | grep -E "\.env|\.key|\.pem|password"
```

**Результат:**
- ✅ `.env` в `.gitignore`
- ✅ `.env.local` в `.gitignore`
- ✅ `*.key` в `.gitignore`
- ✅ `*.pem` в `.gitignore`

### 2. API ключи через переменные окружения ✅

**Проверка:**
```bash
grep -r "API_KEY\s*=" src/ --include="*.py" | grep -v "os.getenv"
```

**Результат:**
- ✅ Все API ключи через `os.getenv()`
- ✅ Нет жестко закодированных секретов

### 3. Пароли БД не в коде ✅

**Проверка:**
```bash
grep -r "postgresql://.*:.*@" src/ --include="*.py"
```

**Результат:**
- ✅ DATABASE_URL через переменные окружения
- ✅ Пароли не в коде

### 4. Sentry фильтрует чувствительные данные ✅

**Файл:** `src/sentry_integration.py`

**Фильтруются:**
- `api_key`, `password`, `token`
- `bybit_api_key`, `bybit_api_secret`
- `telegram_bot_token`
- И другие чувствительные поля

### 5. .gitignore правильный ✅

**Игнорируются:**
```
.env
*.key
*.pem
*.db
logs/
artifacts/
*.pkl
catboost_info/
mlruns/
```

---

## 🚨 ЧТО НУЖНО СДЕЛАТЬ НА СЕРВЕРЕ

### 1. Создать .env с безопасными паролями

```bash
# На сервере
cd ~/myAssistent
cp env.production.example .env

# Сгенерировать пароли
openssl rand -hex 32  # для API_KEY
openssl rand -hex 32  # для POSTGRES_PASSWORD
openssl rand -hex 16  # для MLFLOW_PASSWORD
openssl rand -hex 16  # для GRAFANA_PASSWORD

# Отредактировать .env
nano .env
# Вставить сгенерированные пароли
```

### 2. Настроить Firewall

```bash
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 8000/tcp   # API
sudo ufw allow 5000/tcp   # MLflow
sudo ufw allow 3001/tcp   # Grafana
sudo ufw allow 9090/tcp   # Prometheus

sudo ufw enable
sudo ufw status
```

### 3. Сменить root пароль

```bash
passwd
# Ввести новый сложный пароль
```

### 4. Создать обычного пользователя

```bash
adduser tradingbot
usermod -aG sudo tradingbot
```

### 5. Настроить SSH ключ (опционально)

**На Windows:**
```powershell
ssh-keygen -t ed25519
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh tradingbot@185.73.215.38 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

---

## ⚠️ РИСКИ И ЗАЩИТА

### Риск 1: Утечка .env файла

**Защита:**
- ✅ `.env` в `.gitignore`
- ✅ Не коммитим `.env` в Git
- ✅ На сервере права: `chmod 600 .env`

### Риск 2: Слабые пароли

**Защита:**
- ✅ Генерируем криптографически стойкие пароли
- ✅ Минимум 32 символа для критичных (БД, API)
- ✅ Минимум 16 символов для остальных

### Риск 3: Открытые порты

**Защита:**
- ✅ Firewall (ufw) разрешает только нужные порты
- ✅ SSH на порту 22 (можно сменить на нестандартный)
- ✅ API защищен API_KEY

### Риск 4: Root доступ

**Защита:**
- ✅ Создан пользователь `tradingbot`
- ✅ Работаем от пользователя, а не root
- ✅ sudo только когда нужно

### Риск 5: Логи с секретами

**Защита:**
- ✅ Sentry фильтрует чувствительные поля
- ✅ Логи не коммитятся (в `.gitignore`)
- ✅ На сервере права на логи: `chmod 640 logs/`

---

## 📋 ФИНАЛЬНАЯ ПРОВЕРКА

**Перед запуском на сервере:**

- [ ] `.env` создан и заполнен безопасными паролями
- [ ] `.env` НЕ в Git (`git status --ignored`)
- [ ] Firewall настроен и включен
- [ ] Root пароль изменен
- [ ] Создан пользователь tradingbot
- [ ] SSH ключ настроен (опционально)
- [ ] Права на файлы: `.env` (600), `logs/` (640)
- [ ] Проверено что секреты не в коде
- [ ] Sentry включен и фильтрует секреты

---

## 🔍 КОМАНДЫ ДЛЯ ПРОВЕРКИ

```bash
# Проверить .env не в Git
git ls-files | grep .env
# Должно быть пусто!

# Проверить права на .env
ls -la .env
# Должно быть: -rw------- (600)

# Проверить firewall
sudo ufw status
# Должны быть разрешены только нужные порты

# Проверить что нет секретов в коде
grep -r "password\s*=\s*['\"]" src/
grep -r "api_key\s*=\s*['\"]" src/
# Должно быть пусто!

# Проверить что используем переменные окружения
grep -r "os.getenv" src/ | wc -l
# Должно быть >0
```

---

## ✅ ВСЁ БЕЗОПАСНО!

Если все чеклисты пройдены - можно деплоить! 🚀

**НО ПОМНИ:**
- 🔒 НИКОГДА не коммить `.env` в Git
- 🔒 ВСЕГДА использовать сильные пароли
- 🔒 РЕГУЛЯРНО обновлять систему (`apt-get update && upgrade`)
- 🔒 МОНИТОРИТЬ логи на подозрительную активность



