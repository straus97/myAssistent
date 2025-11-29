# 🚀 Деплой EMA Crossover на Production сервер

**Дата:** 2025-11-29  
**Commit:** 7c743fb  
**Срок:** Запуск в понедельник для 7-дневного paper trading

---

## 📦 Что было сделано

### 1. Улучшенная EMA Crossover стратегия
- **Базовая логика:** EMA(12) × EMA(26) crossover
- **Фильтры:**
  - RSI < 70 (избегаем перекупленности)
  - Volume > 1.2× среднего (подтверждение интереса)
  - ATR для адаптивных Stop-Loss/Take-Profit
- **Risk/Reward:** 2:1 (SL: ATR×1.5, TP: ATR×3.0)

### 2. Backtest результаты (30 дней)
| Символ | Return | Sharpe | Win Rate | Max DD |
|--------|--------|--------|----------|--------|
| BTC/USDT | -0.82% | -1.59 | 33.3% | -1.97% |
| ETH/USDT | +1.31% | 1.48 | 50.0% | -1.13% |
| SOL/USDT | +0.86% | 0.67 | 60.0% | -2.80% |
| **BNB/USDT** | **+1.12%** | **1.55** | **66.7%** | **-1.35%** ✅ |
| **Average** | **+0.62%** | **0.53** | **52.5%** | **-1.81%** |

**Вывод:** BNB/USDT показал лучшие результаты (5/5 критериев). Начинаем с него!

### 3. Новые файлы
- `docs/EMA_CROSSOVER_GUIDE.md` — полная документация
- `scripts/backtest_ema_advanced.py` — бэктест скрипт
- `scripts/monitor_ema_realtime.py` — real-time монитор (60 сек)
- `src/simple_strategies.py` — улучшенная EMA функция
- `artifacts/state/paper_monitor_ema.json` — конфигурация (не в git)

---

## 🔧 Команды для деплоя на сервер

### Шаг 1: Подключиться к серверу

```bash
ssh root@YOUR_SERVER_IP
```

### Шаг 2: Обновить код из GitHub

```bash
cd ~/myAssistent
update-myassistent
```

Эта команда автоматически:
1. Выполняет `git pull`
2. Перезапускает systemd сервис

### Шаг 3: Создать конфигурацию EMA

```bash
cd ~/myAssistent

# Создаём конфиг EMA Crossover
cat > artifacts/state/paper_monitor.json << 'EOF'
{
  "enabled": true,
  "last_update": null,
  "update_interval_minutes": 15,
  "symbols": ["BNB/USDT"],
  "exchange": "bybit",
  "timeframe": "1h",
  "auto_execute": true,
  "use_ml_model": false,
  "use_advanced_ema": true,
  "notifications": true,
  "strategy_params": {
    "fast_period": 12,
    "slow_period": 26,
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "volume_threshold": 1.2,
    "atr_period": 14,
    "atr_stop_loss_multiplier": 1.5,
    "atr_take_profit_multiplier": 3.0
  },
  "stats": {
    "total_updates": 0,
    "total_signals": 0,
    "last_signal_time": null,
    "errors": 0
  }
}
EOF
```

**ВАЖНО:** Начинаем только с **BNB/USDT** (лучшие результаты бэктеста!)

### Шаг 4: Перезапустить сервис

```bash
sudo systemctl restart myassistent
```

### Шаг 5: Проверить статус

```bash
# Логи в реальном времени
journalctl -u myassistent -f

# Статус сервиса
sudo systemctl status myassistent
```

Ожидаемый вывод:
```
[MONITOR] Starting update cycle...
[MONITOR] Generating EMA Crossover signals (Advanced с фильтрами)...
[MONITOR EMA] Generating EMA Crossover Advanced (12/26 + RSI/Vol/ATR) signals for 1 symbols
```

### Шаг 6: Проверить через API

```bash
API_KEY="4ac25807582dae9f9b91396d7ccd223ba796bfdb7077241a994bdeff874b4faf"

# 1. Статус монитора
curl -X GET "http://localhost:8000/paper-monitor/status" \
  -H "X-API-Key: $API_KEY"

# 2. Последние сигналы
curl -X GET "http://localhost:8000/signals/recent?limit=5" \
  -H "X-API-Key: $API_KEY"

# 3. Текущий equity
curl -X GET "http://localhost:8000/trade/equity" \
  -H "X-API-Key: $API_KEY"

# 4. Принудительное обновление
curl -X POST "http://localhost:8000/paper-monitor/update" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"force_update": true}'
```

---

## 📊 Мониторинг (7 дней paper trading)

### Ежедневная проверка (утро + вечер)

```bash
cd ~/myAssistent
./server/daily_monitoring.sh
```

Что проверяется:
- ✅ Сервис работает
- ✅ Цены обновляются
- ✅ Сигналы генерируются
- ✅ Equity растёт
- ✅ Нет критических ошибок

### Real-time монитор (опционально)

Запустить в отдельной сессии:

```bash
cd ~/myAssistent
source .venv/bin/activate
python scripts/monitor_ema_realtime.py
```

Обновляется каждые 60 секунд, показывает:
- Статус монитора
- Текущий equity
- Открытые позиции
- Новые сигналы

---

## ✅ Критерии готовности к Real Trading (через 7 дней)

### Обязательные условия:

1. **Стабильность:**
   - [ ] 7 дней работы без критических ошибок
   - [ ] Все обновления выполнены успешно
   - [ ] Нет gaps в данных

2. **Метрики:**
   - [ ] Sharpe Ratio > 1.0
   - [ ] Max Drawdown < 10%
   - [ ] Win Rate > 40%
   - [ ] Profit Factor > 1.5
   - [ ] Total Return > 0%

3. **Проверки:**
   - [ ] Stop-Loss срабатывает корректно
   - [ ] Take-Profit срабатывает корректно
   - [ ] Telegram уведомления приходят
   - [ ] Equity кривая стабильная

### Если все критерии выполнены:

**Начать Real Trading с малого капитала:**
- Стартовый капитал: **1000₽** (не больше!)
- Символ: **BNB/USDT** (лучшие результаты бэктеста)
- Max позиция: 20% капитала (200₽)
- Daily loss limit: -5% (50₽)

### Если критерии НЕ выполнены:

**Продлить paper trading еще на 7 дней** и оптимизировать:
1. Увеличить `volume_threshold` (меньше ложных сигналов)
2. Добавить фильтр трендовости (ADX > 25)
3. Протестировать другие timeframes (15m, 4h)

---

## 🐛 Troubleshooting

### Проблема: Нет сигналов после деплоя

**Причина:** Недостаточно исторических данных

**Решение:**
```bash
# Загрузить 100 свечей для BNB/USDT
curl -X POST "http://localhost:8000/prices/fetch" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "exchange": "bybit",
    "symbol": "BNB/USDT",
    "timeframe": "1h",
    "limit": 100
  }'

# Проверить количество свечей в БД
curl -X GET "http://localhost:8000/prices/stats/bybit/BNB%2FUSDT/1h" \
  -H "X-API-Key: $API_KEY"
```

### Проблема: Сигналы не исполняются

**Причина:** `auto_execute = false` или trade guard заблокирован

**Решение:**
```bash
# Включить auto_execute
curl -X POST "http://localhost:8000/paper-monitor/toggle-auto-execute" \
  -H "X-API-Key: $API_KEY"

# Проверить trade guard
curl -X GET "http://localhost:8000/trade/guard" \
  -H "X-API-Key: $API_KEY"

# Разблокировать trade guard (если нужно)
curl -X POST "http://localhost:8000/trade/guard/unlock" \
  -H "X-API-Key: $API_KEY"
```

### Проблема: Ошибки в логах

**Проверить логи:**
```bash
# Последние 100 строк
journalctl -u myassistent -n 100

# В реальном времени
journalctl -u myassistent -f
```

**Перезапустить сервис:**
```bash
sudo systemctl restart myassistent
```

---

## 📞 Полезные ссылки

- **Swagger UI:** http://YOUR_SERVER_IP:8000/docs
- **Документация:** `docs/EMA_CROSSOVER_GUIDE.md`
- **Backtest скрипт:** `scripts/backtest_ema_advanced.py`
- **Real-time монитор:** `scripts/monitor_ema_realtime.py`
- **GitHub commit:** https://github.com/straus97/myAssistent/commit/7c743fb

---

## 📅 План на неделю

| День | Действие |
|------|----------|
| **Пн (2 дек)** | Деплой EMA Crossover, запуск paper trading BNB/USDT |
| **Вт-Вс** | Ежедневный мониторинг (утро + вечер) |
| **Вс (8 дек)** | Недельный отчёт, анализ метрик |
| **Пн (9 дек)** | Если критерии выполнены → Real Trading (1000₽) |

---

**Последнее обновление:** 2025-11-29  
**Commit:** 7c743fb  
**Статус:** ✅ ГОТОВО К ДЕПЛОЮ

