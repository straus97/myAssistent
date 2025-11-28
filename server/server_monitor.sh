#!/bin/bash
# Скрипт для мониторинга myAssistent на сервере
# Загрузите этот файл на сервер как monitor.sh

echo "=== МОНИТОРИНГ MYASSISTENT ==="
echo "Время: $(date)"
echo ""

# Проверка статуса сервиса
echo "1. СТАТУС СЕРВИСА:"
systemctl status myassistent --no-pager -l | head -20
echo ""

# Проверка процессов
echo "2. ПРОЦЕССЫ PYTHON:"
ps aux | grep python | grep -v grep
echo ""

# Проверка торговли
echo "3. СТАТУС ТОРГОВЛИ:"
cd ~/myAssistent
if [ -f "artifacts/paper_state.json" ]; then
    echo "Paper Trading State:"
    python3 -c "
import json
try:
    with open('artifacts/paper_state.json', 'r') as f:
        data = json.load(f)
    print(f'Cash: \${data.get(\"cash\", 0):,.2f}')
    print(f'Positions: {len(data.get(\"positions\", []))}')
    print(f'Orders: {len(data.get(\"orders\", []))}')
except Exception as e:
    print(f'Error reading paper state: {e}')
"
else
    echo "Paper state file not found"
fi
echo ""

# Проверка логов
echo "4. ПОСЛЕДНИЕ ЛОГИ (10 строк):"
journalctl -u myassistent -n 10 --no-pager
echo ""

# Проверка дискового пространства
echo "5. ДИСКОВОЕ ПРОСТРАНСТВО:"
df -h ~/myAssistent
echo ""

# Проверка памяти
echo "6. ИСПОЛЬЗОВАНИЕ ПАМЯТИ:"
free -h
echo ""

echo "=== МОНИТОРИНГ ЗАВЕРШЕН ==="
