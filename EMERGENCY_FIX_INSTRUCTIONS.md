# 🚨 ЭКСТРЕННОЕ ИСПРАВЛЕНИЕ MyAssistent

## 📋 ЧТО НУЖНО СДЕЛАТЬ ПРЯМО СЕЙЧАС

### 1. Подключитесь к серверу
```bash
ssh root@vm210211.vds.miran.ru
```

### 2. Перейдите в директорию проекта
```bash
cd ~/myAssistent
```

### 3. Выполните скрипт исправления
```bash
chmod +x fix_critical_issues.sh
./fix_critical_issues.sh
```

### 4. Проверьте результат
```bash
chmod +x daily_monitoring.sh
./daily_monitoring.sh
```

## 📊 ЧТО ДОЛЖНО ПРОИЗОЙТИ

После выполнения скрипта:
- ✅ Остановится сервис
- ✅ Очистятся дублирующиеся данные в БД
- ✅ Закроется старая позиция BTC/USDT
- ✅ Удалятся старые сигналы
- ✅ Перезапустится сервис
- ✅ Обновятся данные цен
- ✅ Обновится монитор

## 🔍 ПРОВЕРКА УСПЕХА

Система работает правильно если:
- ✅ `health` показывает `"status": "ok"`
- ✅ `paper-monitor/status` показывает `"enabled": true`
- ✅ `prices/latest` возвращает данные (не пустой массив)
- ✅ `signals/recent` показывает новые сигналы
- ✅ Нет ошибок `UniqueViolation` в логах

## 📅 ЕЖЕДНЕВНЫЕ ПРОВЕРКИ

### Утром (09:00):
```bash
cd ~/myAssistent
./daily_monitoring.sh
```

### Вечером (21:00):
```bash
cd ~/myAssistent
./daily_monitoring.sh
```

## 🚨 ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

### Перезапуск системы:
```bash
sudo systemctl restart myassistent
```

### Принудительное обновление:
```bash
curl -X POST "http://localhost:8000/prices/fetch" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["BTC/USDT"], "timeframe": "1h", "force_update": true}'

curl -X POST "http://localhost:8000/paper-monitor/update" \
  -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  -H "Content-Type: application/json" \
  -d '{"force_update": true}'
```

### Проверка логов:
```bash
journalctl -u myassistent --no-pager -n 50 | grep -i "error\|exception"
```

## 💰 КРИТИЧНОСТЬ

**Помните:** У вас маленький бюджет, ошибаться нельзя. Если первые торги провалим - проект откладывается до следующего раза.

**Цель:** Стабильная работа системы 7 дней подряд, затем переход к реальной торговле.

---

**Выполните исправления СЕЙЧАС и сообщите о результатах!**
