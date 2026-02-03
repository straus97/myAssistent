#!/bin/bash

# Настройки
API_KEY="5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73"
BASE_URL="http://localhost:8000"
TELEGRAM_BOT_TOKEN="8235999188:AAES2bRkomH-6wpDCxnGTSkX9vamiN5-6co"
TELEGRAM_CHAT_ID="412328488"

# Функция отправки в Telegram
send_telegram() {
    local message="$1"
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d chat_id="${TELEGRAM_CHAT_ID}" \
        -d text="${message}" \
        -d parse_mode="HTML"
}

# Получаем данные
HEALTH=$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/health")
MONITOR=$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/paper-monitor/status")
POSITIONS=$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/trade/positions")
EQUITY=$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/trade/equity")

# Парсим данные
EQUITY_VALUE=$(echo "$EQUITY" | python3 -c "import sys, json; print(json.load(sys.stdin)['equity']['equity'])")
CASH=$(echo "$EQUITY" | python3 -c "import sys, json; print(json.load(sys.stdin)['equity']['cash'])")
POSITIONS_COUNT=$(echo "$EQUITY" | python3 -c "import sys, json; print(json.load(sys.stdin)['equity']['positions_count'])")
TOTAL_UPDATES=$(echo "$MONITOR" | python3 -c "import sys, json; print(json.load(sys.stdin)['stats']['total_updates'])")
TOTAL_SIGNALS=$(echo "$MONITOR" | python3 -c "import sys, json; print(json.load(sys.stdin)['stats']['total_signals'])")
LAST_UPDATE=$(echo "$MONITOR" | python3 -c "import sys, json; print(json.load(sys.stdin)['last_update'])")

# Формируем отчет
REPORT="📊 <b>MyAssistent Daily Report</b>
🕐 $(date '+%Y-%m-%d %H:%M:%S')

💰 <b>Финансы:</b>
• Equity: ${EQUITY_VALUE}
• Cash: ${CASH}
• Позиций: ${POSITIONS_COUNT}

📈 <b>Статистика:</b>
• Обновлений: ${TOTAL_UPDATES}
• Сигналов: ${TOTAL_SIGNALS}
• Последнее обновление: ${LAST_UPDATE}

✅ <b>Статус:</b> Система работает"

# Отправляем в Telegram
send_telegram "$REPORT"
