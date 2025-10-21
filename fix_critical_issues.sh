#!/bin/bash

# Скрипт для исправления критических проблем MyAssistent
# Выполнить на Linux сервере

echo "🚨 ИСПРАВЛЕНИЕ КРИТИЧЕСКИХ ПРОБЛЕМ MyAssistent"
echo "=============================================="

# Переходим в директорию проекта
cd ~/myAssistent

# 1. Останавливаем сервис
echo "1. Останавливаем сервис..."
sudo systemctl stop myassistent

# 2. Очищаем старые позиции (принудительно закрываем позицию от 14 октября)
echo "2. Очищаем старые позиции..."
curl -X POST "http://localhost:8000/trade/close" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC/USDT", "reason": "force_close_old_position"}' || echo "API недоступен, продолжим..."

# 3. Очищаем дублирующиеся данные в таблице prices
echo "3. Очищаем дублирующиеся данные в prices..."
python3 -c "
import sqlite3
import os

# Подключаемся к базе данных
db_path = 'assistant.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Удаляем дублирующиеся записи, оставляя только последние
    cursor.execute('''
        DELETE FROM prices 
        WHERE id NOT IN (
            SELECT MAX(id) 
            FROM prices 
            GROUP BY exchange, symbol, timeframe, ts
        )
    ''')
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f'✅ Удалено {deleted} дублирующихся записей')
else:
    print('❌ База данных не найдена')
"

# 4. Очищаем старые сигналы (старше 3 дней)
echo "4. Очищаем старые сигналы..."
python3 -c "
import sqlite3
import os
from datetime import datetime, timedelta

db_path = 'assistant.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Удаляем сигналы старше 3 дней
    cutoff_date = datetime.now() - timedelta(days=3)
    cursor.execute('DELETE FROM signals WHERE created_at < ?', (cutoff_date,))
    
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    print(f'✅ Удалено {deleted} старых сигналов')
else:
    print('❌ База данных не найдена')
"

# 5. Перезапускаем сервис
echo "5. Перезапускаем сервис..."
sudo systemctl start myassistent
sleep 10

# 6. Проверяем статус
echo "6. Проверяем статус системы..."
curl -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/health | python3 -m json.tool

# 7. Принудительно обновляем данные
echo "7. Принудительно обновляем данные..."
curl -X POST "http://localhost:8000/prices/fetch" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["BTC/USDT"], "timeframe": "1h", "force_update": true, "clear_duplicates": true}'

# 8. Обновляем монитор
echo "8. Обновляем монитор..."
curl -X POST "http://localhost:8000/paper-monitor/update" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{"force_update": true}'

# 9. Проверяем финальный статус
echo "9. Финальная проверка..."
sleep 5
./check_status.sh

echo "✅ ИСПРАВЛЕНИЯ ЗАВЕРШЕНЫ"
echo "Проверьте статус системы через 15 минут"
