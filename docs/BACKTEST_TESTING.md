# 🧪 Тестирование Векторизованного Бэктестинга

## Быстрый старт

### 1. Запуск сервера

```bash
start_server.bat
```

Сервер запустится на http://127.0.0.1:8000

### 2. Открыть Swagger UI

Перейти в браузере: http://127.0.0.1:8000/docs

### 3. Авторизация

1. Нажать кнопку "Authorize" (замок справа вверху)
2. Ввести X-API-Key (из переменной окружения API_KEY)
3. Нажать "Authorize"

---

## Примеры запросов

### POST /backtest/run - Запуск бэктеста

**Минимальный запрос:**

```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01"
}
```

**Полный запрос с настройками:**

```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "model_path": null,
  "signal_threshold": 0.6,
  "initial_capital": 1000.0,
  "commission_bps": 8.0,
  "slippage_bps": 5.0,
  "latency_bars": 1,
  "position_size": 1.0
}
```

**Ожидаемый ответ:**

```json
{
  "success": true,
  "run_id": "backtest_20251010_233045",
  "metrics": {
    "total_return": 0.156,
    "sharpe_ratio": 1.82,
    "sortino_ratio": 2.45,
    "calmar_ratio": 0.95,
    "max_drawdown": -0.164,
    "max_drawdown_duration": 45,
    "max_recovery_time": 67,
    "current_drawdown": -0.023,
    "win_rate": 0.58,
    "avg_win": 0.032,
    "avg_loss": -0.018,
    "profit_factor": 1.84,
    "exposure_time": 0.45,
    "total_trades": 89,
    "benchmark_return": 0.124,
    "excess_return": 0.032
  },
  "equity_curve": [...],
  "trades": [...],
  "benchmark": {
    "benchmark_return": 0.124,
    "benchmark_sharpe": 1.12,
    "benchmark_max_dd": -0.185,
    "outperformance": 0.032,
    "beats_benchmark": true
  }
}
```

### GET /backtest/list - Список бэктестов

**Запрос:**

```
GET /backtest/list?limit=10
```

**Ответ:**

```json
{
  "backtests": [
    {
      "run_id": "backtest_20251010_233045",
      "timestamp": "20251010_233045",
      "metrics": {
        "total_return": 0.156,
        "sharpe_ratio": 1.82,
        "max_drawdown": -0.164,
        "win_rate": 0.58,
        "total_trades": 89
      },
      "config": {...}
    }
  ],
  "total": 1
}
```

### GET /backtest/compare - Сравнить бэктесты

**Запрос:**

```
GET /backtest/compare?run_ids=backtest_20251010_233045,backtest_20251010_234521
```

**Ответ:**

```json
{
  "comparison": [
    {
      "run_id": "backtest_20251010_233045",
      "total_return": 0.156,
      "sharpe_ratio": 1.82,
      "sortino_ratio": 2.45,
      ...
    },
    {
      "run_id": "backtest_20251010_234521",
      "total_return": 0.142,
      "sharpe_ratio": 1.65,
      ...
    }
  ],
  "best": {
    "total_return": "backtest_20251010_233045",
    "sharpe_ratio": "backtest_20251010_233045",
    "sortino_ratio": "backtest_20251010_233045",
    ...
  },
  "count": 2
}
```

---

## Интерпретация метрик

### Критерии успеха

✅ **Хорошая стратегия:**
- Sharpe Ratio > 1.5
- Max Drawdown < 20% (> -0.20)
- Win Rate > 55% (> 0.55)
- Outperforms buy-and-hold (excess_return > 0)

⚠️ **Средняя стратегия:**
- Sharpe Ratio: 1.0 - 1.5
- Max Drawdown: 20-30%
- Win Rate: 50-55%
- Close to buy-and-hold

❌ **Плохая стратегия:**
- Sharpe Ratio < 1.0
- Max Drawdown > 30%
- Win Rate < 50%
- Underperforms buy-and-hold

### Описание метрик

**Total Return** - Общая доходность (0.156 = +15.6%)

**Sharpe Ratio** - Risk-adjusted returns (учитывает волатильность)
- > 1.5: отлично
- 1.0-1.5: хорошо
- 0.5-1.0: средне
- < 0.5: плохо

**Sortino Ratio** - То же что Sharpe, но учитывает только негативную волатильность

**Calmar Ratio** - Доходность / Максимальная просадка

**Max Drawdown** - Максимальная просадка от пика (-0.164 = -16.4%)

**Win Rate** - Доля прибыльных сделок (0.58 = 58%)

**Profit Factor** - Отношение прибыли к убыткам (1.84 = на каждый $1 убытка $1.84 прибыли)

**Exposure Time** - Доля времени в позиции (0.45 = 45% времени в рынке)

---

## Тестовые сценарии

### Сценарий 1: Базовый бэктест на BTC/USDT

```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "initial_capital": 1000.0
}
```

**Что проверяем:**
- Работает ли построение датасета
- Загружается ли модель
- Корректны ли метрики
- Превосходим ли buy-and-hold

### Сценарий 2: Высокий порог сигнала

```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "signal_threshold": 0.7,
  "initial_capital": 1000.0
}
```

**Ожидание:**
- Меньше сделок (total_trades)
- Выше win_rate
- Меньше exposure_time

### Сценарий 3: Высокие комиссии (реалистичный worst-case)

```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "commission_bps": 15.0,
  "slippage_bps": 10.0,
  "initial_capital": 1000.0
}
```

**Ожидание:**
- Ниже total_return
- Ниже sharpe_ratio
- Проверяем устойчивость к издержкам

### Сценарий 4: Частичная позиция (50% капитала)

```json
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "position_size": 0.5,
  "initial_capital": 1000.0
}
```

**Ожидание:**
- Ниже total_return (меньше риска)
- Выше sharpe_ratio (лучше risk-adjusted)
- Ниже max_drawdown (меньше просадки)

---

## Решение проблем

### Ошибка: "Empty dataset"

**Причина:** Нет данных в БД для заданного периода

**Решение:**
1. Загрузить цены: `POST /prices/fetch`
2. Проверить доступность: `GET /prices/available`

### Ошибка: "No model found"

**Причина:** Нет обученной модели в `artifacts/models/`

**Решение:**
1. Обучить модель: `POST /model/train`
2. Или указать model_path явно

### Ошибка: "Insufficient data (< 10 rows)"

**Причина:** Слишком короткий период или нет данных после фильтрации по датам

**Решение:**
1. Расширить диапазон дат
2. Проверить start_date/end_date
3. Загрузить больше исторических данных

### Низкие метрики (Sharpe < 0.5)

**Причины:**
- Модель переобучена (overfitting)
- Недостаточно данных для обучения
- Высокие комиссии/проскальзывание

**Решение:**
1. Переобучить модель на большем датасете
2. Уменьшить signal_threshold для большей селективности
3. Проверить качество модели: `GET /model/current`

---

## Следующие шаги

После успешного тестирования:

1. **Сравнить с paper trading:**
   - Запустить бэктест на тех же датах
   - Сравнить метрики с реальным paper trading

2. **Оптимизация параметров:**
   - Подобрать оптимальный signal_threshold
   - Подобрать оптимальный position_size
   - Проверить разные latency_bars

3. **Перейти к Задаче #2: RL-агент:**
   - Stable-Baselines3 PPO
   - Динамический sizing
   - Hybrid модель (XGBoost + RL)

---

**Дата создания:** 2025-10-10  
**Версия:** 1.0  
**Статус:** Готов к тестированию

