#!/bin/bash
# Диагностика проблемы с данными на сервере Ubuntu

echo "======================================"
echo "1. Проверка статуса сервиса"
echo "======================================"
systemctl status myassistent --no-pager | head -20

echo ""
echo "======================================"
echo "2. Проверка Docker контейнеров"
echo "======================================"
docker ps

echo ""
echo "======================================"
echo "3. Проверка PostgreSQL"
echo "======================================"
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT COUNT(*) as prices_count FROM price;"
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT exchange, symbol, timeframe, COUNT(*) as count FROM price GROUP BY exchange, symbol, timeframe ORDER BY count DESC LIMIT 5;"

echo ""
echo "======================================"
echo "4. Проверка последних логов"
echo "======================================"
journalctl -u myassistent --no-pager -n 50

echo ""
echo "======================================"
echo "5. Тест загрузки данных через API"
echo "======================================"
curl -s -X POST "http://localhost:8000/prices/fetch" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "bybit",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "limit": 100
  }' | python3 -m json.tool

echo ""
echo "======================================"
echo "6. Проверка данных после загрузки"
echo "======================================"
sleep 2
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT COUNT(*) FROM price WHERE symbol = 'BTC/USDT' AND timeframe = '1h';"

echo ""
echo "======================================"
echo "7. Проверка DATABASE_URL в .env"
echo "======================================"
cd /root/myAssistent
grep DATABASE_URL .env

echo ""
echo "======================================"
echo "8. Проверка подключения к БД в приложении"
echo "======================================"
curl -s -X GET "http://localhost:8000/health" | python3 -m json.tool

