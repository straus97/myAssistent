# 📊 Paper Trading Real-Time

> **Цель:** Тестирование стратегии на live данных без риска капитала

---

## 📖 Что это такое?

Paper Trading Real-Time - система автоматического мониторинга и тестирования торговой стратегии на реальных данных в реальном времени без использования реальных денег.

**Возможности:**
- ✅ Автоматическое обновление цен каждые 15 минут
- ✅ Генерация сигналов на новых данных
- ✅ Отслеживание equity в реальном времени
- ✅ История equity для графиков
- ✅ Автоматическое исполнение сигналов (опционально)
- ✅ Telegram уведомления о сигналах
- ✅ Полная статистика работы

---

## 🚀 Быстрый старт

### 1. Запустить монитор

```bash
# Через API
POST http://localhost:8000/paper-monitor/start
X-API-Key: your_api_key

# Ответ
{
  "status": "ok",
  "message": "Monitor started",
  "config": {
    "update_interval_minutes": 15,
    "auto_execute": false
  }
}
```

### 2. Проверить статус

```bash
GET http://localhost:8000/paper-monitor/status
X-API-Key: your_api_key

# Ответ
{
  "enabled": true,
  "last_update": "2025-10-12T15:30:00",
  "update_interval_minutes": 15,
  "auto_execute": false,
  "notifications": true,
  "symbols": ["BTC/USDT"],
  "stats": {
    "total_updates": 42,
    "total_signals": 15,
    "last_signal_time": "2025-10-12T15:15:00",
    "errors": 0
  },
  "equity": {
    "cash": 9500.0,
    "equity": 10250.0,
    "total_pnl": 250.0,
    "n_positions": 2
  },
  "positions_count": 2
}
```

### 3. Посмотреть график equity

```bash
GET http://localhost:8000/paper-monitor/equity/chart?hours=24
X-API-Key: your_api_key

# Ответ
{
  "status": "ok",
  "hours": 24,
  "data_points": 96,
  "data": {
    "timestamps": ["2025-10-11T15:30:00", ...],
    "equity": [10000, 10050, 10100, ...],
    "pnl": [0, 50, 100, ...],
    "pnl_pct": [0, 0.5, 1.0, ...]
  }
}
```

---

## ⚙️ Конфигурация

### Базовые настройки

```bash
POST http://localhost:8000/paper-monitor/config
X-API-Key: your_api_key

{
  "enabled": true,
  "update_interval_minutes": 15,
  "symbols": ["BTC/USDT", "ETH/USDT"],
  "exchange": "bybit",
  "timeframe": "1h",
  "auto_execute": false,
  "notifications": true
}
```

**Параметры:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `enabled` | bool | false | Включить монитор |
| `update_interval_minutes` | int | 15 | Интервал обновления (1-1440) |
| `symbols` | list | ["BTC/USDT"] | Список символов |
| `exchange` | string | "bybit" | Биржа |
| `timeframe` | string | "1h" | Таймфрейм |
| `auto_execute` | bool | false | Авто-исполнение сигналов |
| `notifications` | bool | true | Telegram уведомления |

---

## 🔄 Автоматический режим

Монитор работает автоматически после включения:

### Каждые 15 минут:
1. Обновляет цены для всех символов
2. Генерирует сигналы с использованием текущей модели
3. Проверяет risk-фильтры
4. Исполняет сигналы (если `auto_execute=true`)
5. Обновляет equity позиций
6. Сохраняет snapshot для графика
7. Отправляет уведомления (если есть сигналы)

### Scheduler
Автоматически запускается через APScheduler при старте backend:
```python
# В src/main.py
scheduler.add_job(
    job_paper_monitor,
    IntervalTrigger(minutes=15),
    id="paper_monitor",
    replace_existing=True
)
```

---

## 📊 API Endpoints

### GET /paper-monitor/status
Получить текущий статус монитора

**Response:**
```json
{
  "enabled": true,
  "last_update": "2025-10-12T15:30:00",
  "stats": {
    "total_updates": 42,
    "total_signals": 15
  },
  "equity": {...}
}
```

### POST /paper-monitor/config
Обновить конфигурацию

**Request:**
```json
{
  "enabled": true,
  "symbols": ["BTC/USDT", "ETH/USDT"],
  "auto_execute": false
}
```

### POST /paper-monitor/start
Запустить монитор

### POST /paper-monitor/stop
Остановить монитор

### POST /paper-monitor/update
Запустить обновление вручную (в фоне)

### GET /paper-monitor/equity/chart?hours=24
Получить данные для графика equity

**Parameters:**
- `hours`: Количество часов истории (1-720)

**Response:**
```json
{
  "data": {
    "timestamps": [...],
    "equity": [...],
    "pnl": [...],
    "pnl_pct": [...]
  }
}
```

### GET /paper-monitor/equity/summary
Получить сводку по разным периодам

**Response:**
```json
{
  "summary": {
    "1h": {
      "equity_start": 10000,
      "equity_end": 10050,
      "change": 50,
      "change_pct": 0.5
    },
    "24h": {...},
    "7d": {...},
    "30d": {...}
  }
}
```

### GET /paper-monitor/stats
Получить статистику работы монитора

### DELETE /paper-monitor/history
Очистить историю equity (необратимо!)

---

## 🎯 Типичные сценарии

### Сценарий 1: Простое тестирование (без автоисполнения)

```bash
# 1. Запустить монитор
POST /paper-monitor/start

# 2. Подождать несколько часов

# 3. Проверить сигналы
GET /paper-monitor/stats

# 4. Посмотреть equity
GET /paper-monitor/equity/chart?hours=24

# 5. Остановить
POST /paper-monitor/stop
```

**Результат:** Мониторинг сигналов без реального исполнения

---

### Сценарий 2: Автоматическая торговля (с автоисполнением)

```bash
# 1. Включить авто-исполнение
POST /paper-monitor/config
{
  "enabled": true,
  "auto_execute": true,
  "notifications": true
}

# 2. Запустить
POST /paper-monitor/start

# 3. Мониторить через Telegram уведомления

# 4. Проверять позиции
GET /trade/positions

# 5. Смотреть equity в реальном времени
GET /paper-monitor/equity/chart?hours=24
```

**Результат:** Полностью автоматическая торговля на paper

---

### Сценарий 3: Множественные символы

```bash
# Настроить для нескольких пар
POST /paper-monitor/config
{
  "enabled": true,
  "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
  "auto_execute": true
}
```

**Результат:** Диверсификация сигналов по разным парам

---

## 📈 Мониторинг equity

### История equity
Сохраняется в `artifacts/equity_history_realtime.json`

**Формат:**
```json
[
  {
    "timestamp": "2025-10-12T15:30:00",
    "cash": 9500.0,
    "equity": 10250.0,
    "total_pnl": 250.0,
    "n_positions": 2
  },
  ...
]
```

**Ограничения:**
- Хранятся последние 30 дней (2880 снимков при интервале 15 минут)
- Автоматическая ротация старых данных

### Визуализация
Используйте данные из `/equity/chart` для построения графиков:
- Equity curve
- PnL curve
- PnL %

---

## ⚠️ Важные замечания

### Безопасность

1. **Auto-execute осторожно!**
   - Начните с `auto_execute=false`
   - Изучите генерируемые сигналы
   - Только потом включайте автоисполнение

2. **Risk Management**
   - Убедитесь что настроены риск-фильтры
   - Проверьте `max_open_positions`
   - Установите разумный `buy_fraction`

3. **Мониторинг**
   - Регулярно проверяйте `/stats`
   - Следите за ошибками
   - Проверяйте Telegram уведомления

### Производительность

1. **Интервал обновления**
   - 15 минут - оптимально для 1h timeframe
   - 5-10 минут - для более частых обновлений
   - Слишком частые обновления = лишняя нагрузка

2. **Количество символов**
   - 1-3 символа - быстро
   - 5-10 символов - норм
   - 10+ символов - может быть медленно

3. **Размер истории**
   - 24h = 96 точек (при 15min)
   - 7d = 672 точек
   - 30d = 2880 точек (максимум)

---

## 🐛 Устранение проблем

### "Monitor is disabled"
**Причина:** Монитор не включен  
**Решение:** `POST /paper-monitor/start`

### "No model found"
**Причина:** Нет обученной модели  
**Решение:** Обучите модель через `POST /model/train`

### "Not enough data"
**Причина:** Недостаточно исторических данных  
**Решение:** Загрузите больше данных через `POST /prices/fetch`

### "Errors count increasing"
**Причина:** Ошибки при обновлении  
**Решение:**
1. Проверьте логи: `GET /paper-monitor/stats`
2. Проверьте доступность API бирж
3. Проверьте наличие модели

### "No signals generated"
**Причина:** Модель не находит возможностей  
**Решение:**
1. Проверьте risk policy (может быть слишком строгая)
2. Проверьте качество модели (AUC, Sharpe)
3. Попробуйте другие символы

---

## 📊 Примеры результатов

### Хороший результат ✅
```
После 7 дней мониторинга:
- Total Updates: 672
- Total Signals: 45
- Avg Signals/Day: 6.4
- Equity: $10,450 (+4.5%)
- Max DD: -1.2%
- Win Rate: 62%
```

### Плохой результат ❌
```
После 7 дней мониторинга:
- Total Updates: 672
- Total Signals: 3
- Avg Signals/Day: 0.4
- Equity: $9,850 (-1.5%)
- Errors: 45
```

**Проблема:** Слишком мало сигналов + ошибки  
**Решение:** Проверить модель и риск-фильтры

---

## 🔗 Интеграция с Dashboard

### Frontend пример (React/Next.js)
```typescript
// Получить данные для графика
const response = await fetch(
  'http://localhost:8000/paper-monitor/equity/chart?hours=24',
  {
    headers: {'X-API-Key': apiKey}
  }
);
const {data} = await response.json();

// Построить график с Recharts
<LineChart data={data.timestamps.map((t, i) => ({
  time: t,
  equity: data.equity[i],
  pnl: data.pnl_pct[i]
}))}>
  <Line dataKey="equity" stroke="#10b981" />
  <Line dataKey="pnl" stroke="#3b82f6" />
</LineChart>
```

### Polling для real-time обновлений
```typescript
// Обновлять каждые 60 секунд
useEffect(() => {
  const interval = setInterval(async () => {
    const status = await fetchMonitorStatus();
    setEquity(status.equity);
  }, 60000);
  
  return () => clearInterval(interval);
}, []);
```

---

## 🎯 Следующие шаги

После успешного paper trading:

1. ✅ **Walk-Forward Validation** - убедиться что модель не переобучена
2. ✅ **Paper Trading 30+ дней** - накопить достаточно статистики
3. ✅ **Sharpe > 1.5, DD < 10%** - достичь хороших метрик
4. ⏳ **Risk Management** - добавить stop-loss, take-profit
5. ⏳ **Testnet** - тестировать на Bybit Testnet с реальными API
6. ⏳ **Live Trading** - начать с минимального капитала (5000₽)

---

**Последнее обновление:** 2025-10-12  
**Версия:** 1.0  
**Автор:** AI Assistant

