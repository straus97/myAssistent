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

# Получаем данные за неделю
EQUITY=$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/trade/equity")
MONITOR=$(curl -s -H "X-API-Key: ${API_KEY}" "${BASE_URL}/paper-monitor/status")

# Парсим данные
EQUITY_VALUE=$(echo "$EQUITY" | python3 -c "import sys, json; print(json.load(sys.stdin)['equity']['equity'])")
TOTAL_UPDATES=$(echo "$MONITOR" | python3 -c "import sys, json; print(json.load(sys.stdin)['stats']['total_updates'])")
TOTAL_SIGNALS=$(echo "$MONITOR" | python3 -c "import sys, json; print(json.load(sys.stdin)['stats']['total_signals'])")

# Рассчитываем прибыль
STARTING_CAPITAL=1000
PROFIT=$(echo "$EQUITY_VALUE - $STARTING_CAPITAL" | bc)
PROFIT_PERCENT=$(echo "scale=2; ($PROFIT / $STARTING_CAPITAL) * 100" | bc)

# Формируем недельный отчет
WEEKLY_REPORT="📊 <b>MyAssistent Weekly Report</b>
📅 $(date '+%Y-%m-%d')

💰 <b>Финансовые результаты:</b>
• Начальный капитал: ${STARTING_CAPITAL}
• Текущий капитал: ${EQUITY_VALUE}
• Прибыль: ${PROFIT} (${PROFIT_PERCENT}%)

📈 <b>Активность за неделю:</b>
• Обновлений: ${TOTAL_UPDATES}
• Сигналов: ${TOTAL_SIGNALS}

✅ <b>Статус:</b> Система работает стабильно"

# Отправляем в Telegram
send_telegram "$WEEKLY_REPORT"
