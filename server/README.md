# 🖥️ Server — Серверные Скрипты и Утилиты

Эта папка содержит скрипты для управления и мониторинга MyAssistent на production сервере.

## Основные Скрипты

### Мониторинг
- **daily_monitoring.sh** - Ежедневный мониторинг системы
  ```bash
  ./daily_monitoring.sh
  # Проверяет: статус сервиса, equity, позиции, сигналы, логи
  ```

- **server_diagnostics.sh** - Диагностика сервера
  ```bash
  ./server_diagnostics.sh
  # Выводит: системную информацию, статус сервисов, метрики
  ```

- **server_monitor.sh** - Мониторинг в реальном времени
  ```bash
  ./server_monitor.sh
  # Запускает: watch на ключевые метрики
  ```

### Исправления
- **fix_critical_issues.sh** - Исправление критических проблем
  ```bash
  ./fix_critical_issues.sh
  # Исправляет: UniqueViolation, db locks, restart сервиса
  ```

- **fix_systemd_env.sh** - Исправление environment переменных systemd
  ```bash
  ./fix_systemd_env.sh
  # Обновляет: .env переменные для systemd service
  ```

- **fix_ts_bigint.sql** - SQL скрипт для исправления типов timestamp
  ```sql
  # Исправляет: BIGINT → TIMESTAMP конфликты
  ```

### Deployment
- **setup_server_api.sh** - Начальная настройка сервера
  ```bash
  ./setup_server_api.sh
  # Устанавливает: Python, зависимости, systemd service, nginx
  ```

- **deploy.sh** - Скрипт деплоя (если есть)
  ```bash
  ./deploy.sh
  # Выполняет: git pull, pip install, restart service
  ```

### PowerShell (для локального управления сервером)
- **generate_server_commands.ps1** - Генерация команд для сервера
- **server_commands.ps1** - Набор команд для управления
- **server_quick.ps1** - Быстрые команды
- **setup_ssh_keys.ps1** - Настройка SSH ключей
- **copy_to_server.ps1** - Копирование файлов на сервер

## Использование

### Ежедневная Рутина

**Утренняя проверка (09:00):**
```bash
cd ~/myAssistent/server
./daily_monitoring.sh
```

**Вечерняя проверка (21:00):**
```bash
cd ~/myAssistent/server
./daily_monitoring.sh
```

### При Проблемах

**Если сервис упал:**
```bash
sudo systemctl restart myassistent
sudo systemctl status myassistent
journalctl -u myassistent -f
```

**Если есть критические ошибки:**
```bash
cd ~/myAssistent/server
./fix_critical_issues.sh
```

**Полная диагностика:**
```bash
cd ~/myAssistent/server
./server_diagnostics.sh
```

### Обновление Кода

**Через команду (рекомендуется):**
```bash
update-myassistent
# Выполняет: git pull + pip install + systemctl restart
```

**Вручную:**
```bash
cd ~/myAssistent
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart myassistent
```

## Systemd Service

### Команды управления
```bash
# Статус
sudo systemctl status myassistent

# Запуск
sudo systemctl start myassistent

# Остановка
sudo systemctl stop myassistent

# Перезапуск
sudo systemctl restart myassistent

# Автозапуск
sudo systemctl enable myassistent

# Логи
journalctl -u myassistent -f
journalctl -u myassistent --since "1 hour ago"
```

### Конфигурация
Файл сервиса: `/etc/systemd/system/myassistent.service`

```ini
[Unit]
Description=MyAssistent Trading Bot
After=network.target

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/myAssistent
Environment="PATH=/home/user/myAssistent/.venv/bin"
ExecStart=/home/user/myAssistent/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Мониторинг Метрик

### Ключевые Метрики
- **Equity:** Текущий капитал (начало: $13,530)
- **Позиции:** Количество открытых позиций
- **Сигналы:** Количество сигналов за период
- **Ошибки:** Критические ошибки в логах
- **Uptime:** % времени работы системы

### Где Смотреть
- **Логи:** `journalctl -u myassistent -f`
- **Equity:** API `/trade/equity`
- **Позиции:** API `/trade/positions`
- **Сигналы:** API `/signals/recent`
- **Метрики:** Prometheus (http://server:9090)
- **Дашборд:** Grafana (http://server:3001)

## Troubleshooting

### Проблема: Сервис не запускается
```bash
sudo systemctl status myassistent
journalctl -u myassistent --no-pager -n 50
# Проверить: порт 8000 занят? .env файл? зависимости?
```

### Проблема: Высокая нагрузка
```bash
top  # Проверить CPU/RAM
htop # Детальный мониторинг
ps aux | grep python  # Процессы Python
```

### Проблема: База данных заблокирована
```bash
cd ~/myAssistent
sqlite3 assistant.db ".timeout 5000"
# Или: ./server/fix_critical_issues.sh
```

### Проблема: Нет сигналов
```bash
# Проверить модель
curl http://localhost:8000/model/health -H "X-API-Key: YOUR_KEY"

# Проверить цены
curl http://localhost:8000/prices/latest -H "X-API-Key: YOUR_KEY"

# Проверить watchlist
curl http://localhost:8000/watchlist -H "X-API-Key: YOUR_KEY"
```

## Безопасность

### Файрвол
```bash
sudo ufw status
sudo ufw allow 22      # SSH
sudo ufw allow 8000    # Backend API (только если нужен внешний доступ)
sudo ufw enable
```

### SSH
```bash
# Использовать ключи, не пароли
ssh-keygen -t ed25519 -C "your_email@example.com"

# Отключить password auth в /etc/ssh/sshd_config:
# PasswordAuthentication no
```

### Секреты
- **НЕ** коммитить .env файл
- **НЕ** публиковать API keys
- Использовать переменные окружения
- Регулярно ротировать ключи

## Поддержка

При возникновении проблем:
1. Проверить логи: `journalctl -u myassistent -f`
2. Запустить диагностику: `./server_diagnostics.sh`
3. Попробовать исправления: `./fix_critical_issues.sh`
4. Проверить документацию: `docs/deployment/`
5. Откатить изменения: `git revert` / `git reset`

