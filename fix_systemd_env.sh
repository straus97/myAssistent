#!/bin/bash
# Скрипт для исправления systemd сервиса - добавление DATABASE_URL

echo "Создание нового systemd сервиса с правильным DATABASE_URL..."

cat > /etc/systemd/system/myassistent.service << 'EOF'
[Unit]
Description=MyAssistent Trading Bot
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/myAssistent
Environment="DATABASE_URL=postgresql://myassistent:b7d5e83c415946c5232e5d130f532555cc73d6b1aa69e1429e2a79f5179b265a@localhost:5432/myassistent"
Environment="PATH=/root/myAssistent/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
EnvironmentFile=/root/myAssistent/.env
ExecStart=/root/myAssistent/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "Перезагрузка systemd..."
systemctl daemon-reload

echo "Запуск сервиса..."
systemctl start myassistent

echo "Ожидание 5 секунд..."
sleep 5

echo "Проверка статуса..."
systemctl status myassistent --no-pager

echo ""
echo "Готово! Теперь проверьте:"
echo "1. Загрузите данные: curl -X POST http://localhost:8000/prices/fetch ..."
echo "2. Проверьте в БД: docker exec myassistent_postgres psql -U myassistent -d myassistent -c 'SELECT COUNT(*) FROM prices;'"



