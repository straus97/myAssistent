#!/bin/bash
# Скрипт деплоя на VPS Ubuntu 22.04
# Использование: ./deploy.sh [update|full]

set -e  # Остановить при ошибке

echo "=================================================="
echo "   MyAssistent Deploy Script"
echo "=================================================="
echo ""

MODE=${1:-full}

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функции для красивого вывода
function info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

function error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка что запущено из правильной директории
if [ ! -f "requirements.txt" ]; then
    error "Запусти скрипт из корня проекта!"
    exit 1
fi

# Проверка режима
if [ "$MODE" == "full" ]; then
    info "ПОЛНЫЙ DEPLOY (первый запуск)"
elif [ "$MODE" == "update" ]; then
    info "ОБНОВЛЕНИЕ КОДА (git pull + restart)"
else
    error "Неизвестный режим: $MODE"
    echo "Использование: ./deploy.sh [full|update]"
    exit 1
fi

# ========================================
# ПОЛНЫЙ DEPLOY (первый раз)
# ========================================

if [ "$MODE" == "full" ]; then
    info "Шаг 1/8: Проверка системы..."
    
    # Проверка Ubuntu
    if [ ! -f /etc/lsb-release ]; then
        error "Это не Ubuntu!"
        exit 1
    fi
    
    source /etc/lsb-release
    info "ОС: $DISTRIB_DESCRIPTION"
    
    # Проверка Python 3.10+
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    info "Python: $PYTHON_VERSION"
    
    if (( $(echo "$PYTHON_VERSION < 3.10" | bc -l) )); then
        error "Требуется Python 3.10+, установлен: $PYTHON_VERSION"
        exit 1
    fi
    
    info "Шаг 2/8: Установка системных зависимостей..."
    sudo apt-get update
    sudo apt-get install -y \
        python3-pip \
        python3-venv \
        git \
        docker.io \
        docker-compose \
        postgresql-client \
        curl \
        htop
    
    # Добавить текущего пользователя в группу docker
    sudo usermod -aG docker $USER
    info "Пользователь добавлен в группу docker (требуется перелогин!)"
    
    info "Шаг 3/8: Создание виртуального окружения..."
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    
    info "Шаг 4/8: Установка Python зависимостей..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    info "Шаг 5/8: Проверка .env файла..."
    if [ ! -f ".env" ]; then
        warn ".env файл не найден!"
        info "Скопируй server/.env.production в .env и заполни секреты:"
        echo "  cp server/.env.production .env"
        echo "  nano .env"
        exit 1
    fi
    
    info "Шаг 6/8: Запуск Docker контейнеров..."
    docker-compose up -d postgres mlflow prometheus grafana
    
    # Ждем запуска PostgreSQL
    info "Ожидание запуска PostgreSQL (30 сек)..."
    sleep 30
    
    info "Шаг 7/8: Применение миграций БД..."
    alembic upgrade head
    
    info "Шаг 8/8: Создание systemd service..."
    
    # Создаем systemd service файл
    sudo tee /etc/systemd/system/myassistent.service > /dev/null <<EOF
[Unit]
Description=MyAssistent Trading Bot
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=$(pwd)/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable myassistent
    sudo systemctl start myassistent
    
    info "ПОЛНЫЙ DEPLOY ЗАВЕРШЕН!"
    echo ""
    echo "=================================================="
    echo "   ДОСТУП К СЕРВИСАМ:"
    echo "=================================================="
    echo "API:        http://185.73.215.38:8000/docs"
    echo "MLflow:     http://185.73.215.38:5000"
    echo "Prometheus: http://185.73.215.38:9090"
    echo "Grafana:    http://185.73.215.38:3001"
    echo ""
    echo "Проверка статуса:"
    echo "  sudo systemctl status myassistent"
    echo ""
    echo "Логи:"
    echo "  sudo journalctl -u myassistent -f"
    echo ""

# ========================================
# ОБНОВЛЕНИЕ (git pull + restart)
# ========================================

elif [ "$MODE" == "update" ]; then
    info "Шаг 1/5: Git pull..."
    git pull origin main
    
    info "Шаг 2/5: Активация venv..."
    source .venv/bin/activate
    
    info "Шаг 3/5: Обновление зависимостей..."
    pip install -r requirements.txt --upgrade
    
    info "Шаг 4/5: Применение миграций..."
    alembic upgrade head
    
    info "Шаг 5/5: Перезапуск сервиса..."
    sudo systemctl restart myassistent
    
    info "ОБНОВЛЕНИЕ ЗАВЕРШЕНО!"
    echo ""
    echo "Проверка статуса:"
    echo "  sudo systemctl status myassistent"
fi

echo ""
info "ГОТОВО! 🚀"



