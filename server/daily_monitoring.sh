#!/bin/bash

# Улучшенный скрипт ежедневного мониторинга MyAssistent
# Использовать утром и вечером

echo "📊 MyAssistent - Ежедневный Мониторинг"
echo "======================================"
echo "🕐 $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Переходим в директорию проекта
cd ~/myAssistent

# 1. Проверка здоровья системы
echo "🏥 ПРОВЕРКА ЗДОРОВЬЯ СИСТЕМЫ:"
echo "------------------------------"
health_status=$(curl -s -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/health | python3 -m json.tool)

if [ $? -eq 0 ]; then
    echo "✅ Система работает"
    echo "$health_status"
else
    echo "❌ Система недоступна!"
    echo "Проверьте: sudo systemctl status myassistent"
    exit 1
fi

echo ""

# 2. Статус монитора
echo "📈 СТАТУС PAPER TRADING МОНИТОРА:"
echo "--------------------------------"
monitor_status=$(curl -s -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/paper-monitor/status | python3 -m json.tool)

if [ $? -eq 0 ]; then
    echo "$monitor_status"
    
    # Извлекаем ключевые метрики
    enabled=$(echo "$monitor_status" | python3 -c "import sys, json; data=json.load(sys.stdin); print('✅' if data.get('enabled') else '❌')")
    last_update=$(echo "$monitor_status" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('last_update', 'N/A'))")
    total_signals=$(echo "$monitor_status" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('stats', {}).get('total_signals', 'N/A'))")
    errors=$(echo "$monitor_status" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('stats', {}).get('errors', 'N/A'))")
    
    echo ""
    echo "📊 КЛЮЧЕВЫЕ МЕТРИКИ:"
    echo "  Монитор: $enabled"
    echo "  Последнее обновление: $last_update"
    echo "  Всего сигналов: $total_signals"
    echo "  Ошибки: $errors"
else
    echo "❌ Не удалось получить статус монитора"
fi

echo ""

# 3. Проверка позиций
echo "💰 ОТКРЫТЫЕ ПОЗИЦИИ:"
echo "-------------------"
positions=$(curl -s -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/trade/positions | python3 -m json.tool)

if [ $? -eq 0 ]; then
    echo "$positions"
    
    # Проверяем количество позиций
    pos_count=$(echo "$positions" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('positions', [])))")
    
    if [ "$pos_count" -gt 0 ]; then
        echo ""
        echo "⚠️  ВНИМАНИЕ: Открыто $pos_count позиций"
        
        # Проверяем возраст позиций
        echo "$positions" | python3 -c "
import sys, json
from datetime import datetime

data = json.load(sys.stdin)
for pos in data.get('positions', []):
    opened_at = pos.get('opened_at', '')
    if opened_at:
        try:
            opened_dt = datetime.fromisoformat(opened_at.replace('Z', '+00:00'))
            age_hours = (datetime.now().replace(tzinfo=opened_dt.tzinfo) - opened_dt).total_seconds() / 3600
            if age_hours > 72:
                print(f'🚨 Позиция {pos.get(\"symbol\")} слишком старая: {age_hours:.1f} часов')
            elif age_hours > 48:
                print(f'⚠️  Позиция {pos.get(\"symbol\")} старая: {age_hours:.1f} часов')
        except:
            pass
"
    else
        echo "✅ Нет открытых позиций"
    fi
else
    echo "❌ Не удалось получить информацию о позициях"
fi

echo ""

# 4. Последние сигналы
echo "📡 ПОСЛЕДНИЕ СИГНАЛЫ (5):"
echo "------------------------"
recent_signals=$(curl -s -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  "http://localhost:8000/signals/recent?limit=5" | python3 -m json.tool)

if [ $? -eq 0 ]; then
    echo "$recent_signals"
    
    # Проверяем свежесть сигналов
    echo ""
    echo "🕐 АНАЛИЗ СВЕЖЕСТИ СИГНАЛОВ:"
    echo "$recent_signals" | python3 -c "
import sys, json
from datetime import datetime

data = json.load(sys.stdin)
if data:
    latest_signal = data[0]
    created_at = latest_signal.get('created_at', '')
    if created_at:
        try:
            signal_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            age_hours = (datetime.now().replace(tzinfo=signal_dt.tzinfo) - signal_dt).total_seconds() / 3600
            
            if age_hours < 1:
                print(f'✅ Последний сигнал свежий: {age_hours:.1f} часов назад')
            elif age_hours < 6:
                print(f'⚠️  Последний сигнал недавний: {age_hours:.1f} часов назад')
            else:
                print(f'🚨 Последний сигнал старый: {age_hours:.1f} часов назад')
                print('   Возможна проблема с генерацией сигналов!')
        except:
            print('❌ Не удалось проанализировать время сигнала')
else:
    print('❌ Нет сигналов')
"
else
    echo "❌ Не удалось получить последние сигналы"
fi

echo ""

# 5. Проверка логов на ошибки
echo "📋 ПРОВЕРКА ЛОГОВ (последние 50 строк):"
echo "--------------------------------------"
recent_logs=$(journalctl -u myassistent --no-pager -n 50 | grep -i "error\|exception\|traceback\|failed" | tail -10)

if [ -n "$recent_logs" ]; then
    echo "🚨 НАЙДЕНЫ ОШИБКИ:"
    echo "$recent_logs"
else
    echo "✅ Критических ошибок не найдено"
fi

echo ""

# 6. Проверка свежести данных
echo "📊 ПРОВЕРКА СВЕЖЕСТИ ДАННЫХ:"
echo "----------------------------"
latest_prices=$(curl -s -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  "http://localhost:8000/prices/latest?symbol=BTC/USDT&timeframe=1h&limit=1" | python3 -m json.tool)

if [ $? -eq 0 ]; then
    data_count=$(echo "$latest_prices" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('data', [])))")
    
    if [ "$data_count" -gt 0 ]; then
        echo "✅ Данные цен доступны ($data_count записей)"
        echo "$latest_prices"
    else
        echo "🚨 НЕТ ДАННЫХ О ЦЕНАХ!"
        echo "Возможна проблема с загрузкой данных"
    fi
else
    echo "❌ Не удалось проверить данные цен"
fi

echo ""

# 7. Рекомендации
echo "💡 РЕКОМЕНДАЦИИ:"
echo "----------------"

# Проверяем различные условия и даем рекомендации
if [ "$errors" != "N/A" ] && [ "$errors" -gt 0 ]; then
    echo "🚨 Есть ошибки в мониторе - проверьте логи"
fi

if [ "$pos_count" -gt 0 ]; then
    echo "💰 Есть открытые позиции - следите за рисками"
fi

# Проверяем время последнего обновления
if [ "$last_update" != "N/A" ]; then
    echo "$monitor_status" | python3 -c "
import sys, json
from datetime import datetime

data = json.load(sys.stdin)
last_update = data.get('last_update', '')
if last_update:
    try:
        update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
        age_minutes = (datetime.now().replace(tzinfo=update_dt.tzinfo) - update_dt).total_seconds() / 60
        
        if age_minutes > 30:
            print(f'⚠️  Монитор не обновлялся {age_minutes:.0f} минут')
            print('   Рекомендуется принудительное обновление')
        else:
            print('✅ Монитор обновляется регулярно')
    except:
        pass
"
fi

echo ""
echo "🔄 КОМАНДЫ ДЛЯ ПРИНУДИТЕЛЬНОГО ОБНОВЛЕНИЯ:"
echo "----------------------------------------"
echo "curl -X POST \"http://localhost:8000/prices/fetch\" \\"
echo "  -H \"X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"symbols\": [\"BTC/USDT\"], \"timeframe\": \"1h\", \"force_update\": true}'"
echo ""
echo "curl -X POST \"http://localhost:8000/paper-monitor/update\" \\"
echo "  -H \"X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73\" \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"force_update\": true}'"

echo ""
echo "📅 СЛЕДУЮЩАЯ ПРОВЕРКА:"
echo "---------------------"
echo "Утром: $(date -d '+1 day' '+%Y-%m-%d') 09:00"
echo "Вечером: $(date '+%Y-%m-%d') 21:00"
echo ""
echo "✅ МОНИТОРИНГ ЗАВЕРШЕН"
