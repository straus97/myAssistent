# 🔬 Walk-Forward Validation

> **Цель:** Проверить модель на разных временных окнах для защиты от overfitting

---

## 📖 Что это такое?

Walk-Forward Validation (WFV) — метод проверки торговых стратегий, который:
1. Разбивает датасет на последовательные временные окна
2. Обучает модель на каждом train окне (например, 30 дней)
3. Тестирует на следующем test окне (например, 7 дней)
4. Агрегирует метрики по всем окнам

**Преимущества:**
- ✅ Защита от overfitting на конкретном периоде
- ✅ Проверка стабильности модели во времени
- ✅ Реалистичная оценка производительности
- ✅ Обнаружение regime changes (изменений рынка)

---

## 🚀 Использование

### Через скрипт (консоль)

```bash
python scripts/walk_forward_validation.py
```

**Параметры в скрипте:**
- `window_train_days`: 30 дней (размер train окна)
- `window_test_days`: 7 дней (размер test окна)
- `step_days`: 7 дней (шаг смещения окна)
- `symbol`: BTC/USDT
- `timeframe`: 1h
- `limit`: 3000 свечей (~125 дней для 1h)

**Вывод:**
```
[1/4] Загрузка данных...
✅ Загружено 2976 свечей

[2/4] Создание фичей...
✅ Создано 38 фичей, 2808 строк после очистки

[3/4] Запуск валидации...
🔬 Walk-Forward Validation
Train window: 30 дней (720 баров)
Test window: 7 дней (168 баров)
Step: 7 дней (168 баров)

[4/4] Анализ результатов...
📊 АНАЛИЗ РЕЗУЛЬТАТОВ
Количество окон: 10

📈 Агрегированные метрики (по окнам):
  Average Return: 0.0245 (2.45%)
  Std Return: 0.0378 (3.78%)
  Average Sharpe: 1.23
  Profitable Windows: 7/10 (70.0%)

🌍 Глобальные метрики (вся equity curve):
  Total Return: 0.1234 (12.34%)
  Global Sharpe: 1.56

🎯 ОЦЕНКА КРИТЕРИЕВ УСПЕХА:
✓ Average Return >= 3%: ❌ НЕТ (2.45%)
✓ Average Sharpe >= 1.0: ✅ ДА (1.23)
✓ Std Return <= 5%: ✅ ДА (3.78%)
✓ Profitable Windows >= 60%: ✅ ДА (70.0%)

💾 Результаты сохранены: artifacts/validation/walk_forward_20251012_150000.json
```

---

### Через API

#### 1. Запустить валидацию

```bash
POST /validation/walk-forward
X-API-Key: your_api_key

{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h",
  "limit": 3000,
  "window_train_days": 30,
  "window_test_days": 7,
  "step_days": 7,
  "commission_bps": 8.0,
  "slippage_bps": 5.0
}
```

**Ответ:**
```json
{
  "success": true,
  "run_id": "20251012_150000",
  "message": "Walk-Forward валидация завершена",
  "summary": {
    "avg_return": 0.0245,
    "std_return": 0.0378,
    "avg_sharpe": 1.23,
    "profitable_pct": 70.0,
    "global_return": 0.1234,
    "global_sharpe": 1.56,
    "all_criteria_met": false
  },
  "n_windows": 10,
  "results_file": "artifacts/validation/walk_forward_20251012_150000.json"
}
```

#### 2. Получить список валидаций

```bash
GET /validation/results
X-API-Key: your_api_key
```

**Ответ:**
```json
[
  {
    "run_id": "20251012_150000",
    "timestamp": "2025-10-12T15:00:00",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "n_windows": 10,
    "avg_return": 0.0245,
    "avg_sharpe": 1.23,
    "global_return": 0.1234,
    "profitable_pct": 70.0,
    "all_criteria_met": false
  },
  ...
]
```

#### 3. Получить детали валидации

```bash
GET /validation/results/{run_id}
X-API-Key: your_api_key
```

**Ответ:** Полный JSON с метриками по каждому окну, глобальными метриками и конфигурацией.

#### 4. Получить последнюю валидацию

```bash
GET /validation/latest
X-API-Key: your_api_key
```

#### 5. Удалить валидацию

```bash
DELETE /validation/results/{run_id}
X-API-Key: your_api_key
```

---

## 📊 Критерии успеха

| Метрика | Целевое значение | Описание |
|---------|-----------------|----------|
| **Average Return** | ≥ 3% | Средняя доходность по всем окнам |
| **Average Sharpe** | ≥ 1.0 | Средний Sharpe ratio (risk-adjusted return) |
| **Std Return** | ≤ 5% | Стандартное отклонение доходности (стабильность) |
| **Profitable Windows** | ≥ 60% | Доля прибыльных окон |

**Если все критерии выполнены:**
```
🎉 ВСЕ КРИТЕРИИ ДОСТИГНУТЫ! Модель устойчива к overfitting!
```

---

## 🔍 Интерпретация результатов

### 1. Average Return (средняя доходность)

- **Цель:** ≥ 3%
- **Что показывает:** Средняя прибыль по всем test окнам
- **Если ниже цели:** Модель недостаточно прибыльна на новых данных

### 2. Average Sharpe (средний Sharpe ratio)

- **Цель:** ≥ 1.0
- **Что показывает:** Risk-adjusted returns (доходность с учётом риска)
- **Если ниже цели:** Слишком высокая волатильность относительно доходности

### 3. Std Return (стандартное отклонение доходности)

- **Цель:** ≤ 5%
- **Что показывает:** Стабильность результатов во времени
- **Если выше цели:** Модель нестабильна, результаты сильно варьируются

### 4. Profitable Windows (доля прибыльных окон)

- **Цель:** ≥ 60%
- **Что показывает:** Консистентность модели
- **Если ниже цели:** Модель прибыльна не на всех периодах (риск убытков)

### 5. Global Return (глобальная доходность)

- **Описание:** Доходность агрегированной equity curve (все окна как единая стратегия)
- **Сравнение:** Должна быть близка к Average Return × n_windows

---

## 🛠️ Настройка параметров

### Размер окон

**Рекомендации:**
- **Крипто 1h:** train=30 дней, test=7 дней, step=7 дней
- **Крипто 4h:** train=60 дней, test=14 дней, step=14 дней
- **Крипто 1d:** train=180 дней, test=30 дней, step=30 дней
- **Форекс 1h:** train=90 дней, test=14 дней, step=7 дней

**Принципы:**
- Train window должно быть достаточно большим для обучения (~500-1000 баров)
- Test window должно быть достаточно большим для статистики (~50-200 баров)
- Step < test_window = overlapping windows (более сглаженные результаты)
- Step = test_window = non-overlapping windows (более независимые окна)

### Комиссии и проскальзывание

**Рекомендации:**
- **Bybit Spot:** commission=8 bps, slippage=5 bps
- **Bybit Futures:** commission=6 bps, slippage=3 bps (maker)
- **Binance Spot:** commission=10 bps, slippage=5 bps
- **Binance Futures:** commission=4 bps, slippage=3 bps (maker)

---

## ⚠️ Частые проблемы

### 1. "Недостаточно данных: X строк (нужно минимум 1000)"

**Причина:** Слишком мало свечей загружено  
**Решение:** Увеличьте `limit` в запросе (например, 5000)

### 2. "Не все критерии достигнуты"

**Причины:**
- Модель переобучена на конкретном периоде
- Недостаточно фичей для обобщения
- Слишком агрессивные параметры (большой размер позиций)
- Рынок изменился (regime change)

**Решения:**
- Увеличьте количество фичей (on-chain, macro, news)
- Снизьте агрессивность позиционирования
- Добавьте regularization (увеличьте min_child_weight в XGBoost)
- Используйте более короткие train windows (адаптация к новым условиям)

### 3. "Profitable Windows < 60%"

**Причина:** Модель нестабильна во времени  
**Решение:**
- Добавьте фичи, которые работают в разных market regimes
- Используйте ensemble моделей (XGBoost + LightGBM + CatBoost)
- Добавьте market regime detection (bull/bear/sideways)

---

## 📈 Примеры результатов

### Отличная модель ✅

```
Average Return: 5.2% (цель 3%)
Average Sharpe: 1.8 (цель 1.0)
Std Return: 2.1% (цель 5%)
Profitable Windows: 8/10 (80%)
Global Return: 14.3%
```

**Вывод:** Модель стабильна, прибыльна и готова к production!

### Переобученная модель ❌

```
Average Return: -1.2% (цель 3%)
Average Sharpe: -0.5 (цель 1.0)
Std Return: 8.3% (цель 5%)
Profitable Windows: 3/10 (30%)
Global Return: -5.4%
```

**Вывод:** Модель переобучена, не работает на новых данных. Требуется полная переработка.

### Нестабильная модель ⚠️

```
Average Return: 4.1% (цель 3%)
Average Sharpe: 1.2 (цель 1.0)
Std Return: 9.7% (цель 5%)
Profitable Windows: 5/10 (50%)
Global Return: 7.8%
```

**Вывод:** Модель прибыльна, но нестабильна. Результаты сильно варьируются во времени. Требуется улучшение консистентности.

---

## 🎯 Следующие шаги

После успешной Walk-Forward Validation:

1. ✅ **Paper Trading** — тестирование на live данных без риска
2. ✅ **Risk Management** — добавление stop-loss, take-profit, max exposure
3. ✅ **Testnet проверка** — 100+ сделок на Bybit Testnet
4. ✅ **Live Trading** — реальная торговля с минимальным капиталом (5000₽)

---

**Последнее обновление:** 2025-10-12  
**Версия:** 1.0  
**Автор:** AI Assistant

