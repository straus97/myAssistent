# 📊 Ежедневный чек-лист мониторинга MyAssistent Trading Bot

## 🕐 **ЕЖЕДНЕВНЫЕ ПРОВЕРКИ (5-10 минут)**

### 1. **Быстрая проверка статуса системы**
```bash
# Запустите скрипт проверки
./check_status.sh
```

**Что проверить:**
- ✅ **Status: ok** - система работает
- ✅ **Database: ok** - база данных доступна
- ✅ **Scheduler: ok** - планировщик работает
- ✅ **Model: ok** - ML модель загружена

### 2. **Проверка Paper Trading Monitor**
```bash
# Проверьте статус monitor
curl -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/paper-monitor/status | python3 -m json.tool
```

**Что проверить:**
- ✅ **enabled: true** - monitor включён
- ✅ **use_ml_model: true** - используется ML модель
- ✅ **auto_execute: true** - автоисполнение включено
- ✅ **last_update** - не старше 30 минут
- ✅ **total_signals** - увеличивается
- ✅ **errors: 0** - нет ошибок

### 3. **Проверка позиций и эквити**
```bash
# Проверьте позиции
curl -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/trade/positions | python3 -m json.tool
```

**Что проверить:**
- 📈 **Количество позиций** - логично ли?
- 💰 **PnL** - прибыль/убыток
- 📊 **Equity** - общая стоимость портфеля

### 4. **Проверка последних сигналов**
```bash
# Проверьте последние сигналы
curl -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  "http://localhost:8000/signals/recent?limit=3" | python3 -m json.tool
```

**Что проверить:**
- 🔔 **Свежие сигналы** - не старше 24 часов
- 📈 **Высокая вероятность** - prob_up > 0.7
- 🎯 **Правильные символы** - BTC/USDT, SOL/USDT

## 🔧 **ЕЖЕНЕДЕЛЬНЫЕ ПРОВЕРКИ (15-20 минут)**

### 1. **Проверка логов системы**
```bash
# Проверьте логи за последние 24 часа
journalctl -u myassistent --no-pager --since "24 hours ago" | grep -i "error\|warning\|failed"
```

### 2. **Проверка производительности модели**
```bash
# Проверьте метрики модели
curl -H "X-API-Key: 5fa613c18a92d0d69d3bf5a5f7d72396cd5cca41ed0bc1d058db499107ba6f73" \
  http://localhost:8000/models/latest | python3 -m json.tool
```

### 3. **Проверка данных**
```bash
# Проверьте количество данных
docker exec myassistent_postgres psql -U myassistent -d myassistent -c \
  "SELECT symbol, timeframe, COUNT(*) as candles FROM prices GROUP BY symbol, timeframe ORDER BY candles DESC;"
```

## 🚨 **КРИТИЧЕСКИЕ ПРОВЕРКИ (при проблемах)**

### 1. **Проверка сервиса**
```bash
# Проверьте статус сервиса
systemctl status myassistent --no-pager
```

### 2. **Проверка базы данных**
```bash
# Проверьте подключение к БД
docker exec myassistent_postgres psql -U myassistent -d myassistent -c "SELECT 1;"
```

### 3. **Проверка модели**
```bash
# Проверьте наличие модели
ls -la artifacts/models/*.pkl
```

### 4. **Перезапуск при необходимости**
```bash
# Перезапустите сервис
sudo systemctl restart myassistent
sleep 10
./check_status.sh
```

## 📊 **МЕТРИКИ ДЛЯ ОТСЛЕЖИВАНИЯ**

### **Ежедневные метрики:**
- Количество сигналов за день
- Количество открытых/закрытых позиций
- PnL за день
- Количество ошибок

### **Еженедельные метрики:**
- Общий PnL за неделю
- Sharpe ratio
- Максимальная просадка
- Точность сигналов

### **Ежемесячные метрики:**
- Общая доходность
- Сравнение с бенчмарком
- Стабильность работы системы
- Необходимость переобучения модели

## 🎯 **КРИТЕРИИ УСПЕХА**

### **Система работает хорошо, если:**
- ✅ Нет ошибок в логах
- ✅ Monitor обновляется каждые 15 минут
- ✅ Генерируются свежие сигналы
- ✅ PnL положительный или стабильный
- ✅ Модель показывает высокую точность (>70%)

### **Требуется внимание, если:**
- ⚠️ Monitor не обновляется >30 минут
- ⚠️ Нет новых сигналов >24 часов
- ⚠️ Много ошибок в логах
- ⚠️ PnL сильно отрицательный
- ⚠️ Модель показывает низкую точность (<60%)

## 📞 **КОНТАКТЫ ДЛЯ ПОДДЕРЖКИ**

- **Логи системы:** `journalctl -u myassistent --no-pager -n 100`
- **Статус сервиса:** `systemctl status myassistent`
- **Проверка здоровья:** `curl http://localhost:8000/health`
- **API документация:** `http://localhost:8000/docs`

---

**💡 Совет:** Сохраните этот чек-лист и проверяйте систему каждый день в одно и то же время для лучшего контроля.
