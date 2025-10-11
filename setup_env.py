"""
Скрипт для создания .env файла с корректными настройками
Запуск: python setup_env.py
"""
import os
from pathlib import Path

def create_env_file():
    """Создаёт .env файл с базовыми настройками"""
    env_path = Path(".env")
    
    if env_path.exists():
        response = input("⚠️  Файл .env уже существует. Перезаписать? (y/N): ")
        if response.lower() != 'y':
            print("❌ Отменено. Файл .env не изменён.")
            return
    
    env_content = """# Environment Configuration
# Автоматически создан setup_env.py

# Environment
ENV=dev

# API Settings
API_BASE_URL=http://127.0.0.1:8000
API_KEY=dev_api_key_for_testing_only

# Database Configuration
# SQLite (по умолчанию для разработки):
DATABASE_URL=sqlite:///./assistant.db

# PostgreSQL (для продакшна, запустите docker-compose up -d postgres):
# DATABASE_URL=postgresql://myassistent:change_me_in_production@localhost:5432/myassistent

# MLflow Tracking
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_USERNAME=admin
MLFLOW_PASSWORD=admin

# Prometheus & Grafana
ENABLE_METRICS=true
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin

# Logging
LOG_DIR=./logs
LOG_LEVEL=INFO

# Artifacts & Models
ARTIFACTS_DIR=./artifacts

# Telegram Notifications (опционально)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# News API (опционально)
NEWS_API_KEY=

# Bybit Exchange API (для реальной торговли - пока не используется)
BYBIT_API_KEY=
BYBIT_API_SECRET=
BYBIT_TESTNET=true

# Trade Settings
TRADE_MODE=live

# UI Settings
OFFLINE_DOCS=1
ENABLE_DOCS=1

# Automation Settings
APP_AUTOMATION_CONCURRENCY=1
PRICES_EVERY_MIN=3
MODELS_DAILY_UTC=03:20
REPORT_DAILY_UTC=03:50
HORIZON_STEPS=12

# Discovery Settings
DISCOVER_MIN_VOL_USD=2000000
DISCOVER_TOP_N=25
DISCOVER_QUOTES=USDT
DISCOVER_TIMEFRAMES=15m
DISCOVER_LIMIT=1000
DISCOVER_EXCHANGES=binance,bybit

# Timezone
TZ=UTC
"""
    
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    
    print("✅ Файл .env создан успешно!")
    print("\n📋 Ключевые настройки:")
    print("   - DATABASE_URL: sqlite:///./assistant.db (SQLite по умолчанию)")
    print("   - MLFLOW_TRACKING_URI: http://localhost:5000 ✅")
    print("   - ENABLE_METRICS: true ✅")
    print("   - API_KEY: dev_api_key_for_testing_only")
    print("\n💡 Рекомендации:")
    print("   1. Для продакшна смени API_KEY (генерируй через: openssl rand -hex 32)")
    print("   2. Для PostgreSQL раскомментируй DATABASE_URL с postgresql://")
    print("   3. Для Telegram уведомлений добавь TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")


if __name__ == "__main__":
    print("="*70)
    print("🔧 СОЗДАНИЕ .env ФАЙЛА")
    print("="*70 + "\n")
    create_env_file()
    print("\n" + "="*70)

