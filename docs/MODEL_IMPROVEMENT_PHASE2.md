# 🚀 MODEL IMPROVEMENT - PHASE 2: Feature Selection + Hyperparameter Optimization

**Дата:** 2025-10-12  
**Статус:** 🔄 В процессе (Optuna optimization запущен)

---

## 📋 Цели PHASE 2

### Критичные (Must Have)
- ✅ Feature Selection - убрать 28 статичных фичей (on-chain, macro, social)
- 🔄 Optuna hyperparameter tuning с 150 trials (по 50 на модель)
- ⏳ Выбор лучшей модели по ROC AUC

### Целевые (Should Have)
- ⏳ Backtest: Sharpe >1.0 (допустимо 0.8+)
- ⏳ Backtest: Return >3% (допустимо 1%+)
- ⏳ Win Rate >50%
- ⏳ Profit Factor >1.2

### Идеальные (Nice to Have)
- ⏳ Backtest: Sharpe >1.5
- ⏳ Backtest: Return >5%
- ⏳ Max Drawdown <10%
- ⏳ Ensemble превосходит single models

---

## 🎯 Выполненные задачи

### 1. ✅ Unicode Error Fix

**Проблема:**
```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'
```

**Решение:**
Заменил символ `→` на ASCII-совместимый `->` в `scripts/train_ensemble_optimized.py:167`

---

### 2. ✅ Feature Selection (убрано 28 статичных фичей)

**Проблема PHASE 1:**
- On-chain (13 фичей), Macro (9 фичей), Social (6 фичей) - статичные
- Одинаковые значения для всего датасета (вызываются один раз)
- ROC AUC был 0.4848 (хуже случайного)
- Модель убыточна: Sharpe -1.98, Return -2.56%

**Что сделано:**
1. Закомментированы блоки получения данных в `src/features.py`:
   - On-chain метрики (строки 269-289)
   - Макроэкономические данные (строки 291-306)
   - Social signals (строки 308-322)

2. Закомментированы соответствующие списки в feature_cols (строки 418-437)

3. Обновлены print-сообщения для отображения изменений

**Результат:**
- Было: 112 фичей (84 динамических + 28 статичных)
- Стало: **84 динамических фичей** (100% dynamic)
- Убрано: 28 статичных фичей, которые не дают value

**Оставшиеся фичи:**
- Base price features (6): close, volume, ret_1, vol_norm, skew_5, kurt_5
- Lag features (12): ret_1_lag1-4, rsi_14_lag1-4, bb_pct_lag1, vol_norm_lag1-4, momentum
- Time features (11): hour, day_of_week, day_of_month, month, cyclical encoding, binary flags
- Technical indicators (37): RSI, MACD, Bollinger Bands, ATR, ADX, Stochastic, Williams %R, CCI, EMA crossovers, volume ratios, price action, volatility, trend
- News features (18): news_cnt, sent_mean, tag_* (6h, 24h windows)

---

### 3. ✅ Optuna Configuration Update

**Изменения в `scripts/train_ensemble_optimized.py`:**

```python
# Было:
N_TRIALS = 30   # 10 trials на модель
TIMEOUT = 1800  # 30 минут

# Стало:
N_TRIALS = 150  # 50 trials на модель
TIMEOUT = 7200  # 2 часа
```

**Дополнительные улучшения:**
- Добавлено подавление warnings для чистого вывода
- Установлен Optuna logging level = WARNING
- Оптимизация параметров для каждой модели:
  - **XGBoost**: n_estimators, max_depth, learning_rate, subsample, colsample_bytree, min_child_weight, gamma, reg_alpha, reg_lambda
  - **LightGBM**: n_estimators, max_depth, learning_rate, subsample, colsample_bytree, min_child_samples, num_leaves, reg_alpha, reg_lambda
  - **CatBoost**: iterations, depth, learning_rate, subsample, l2_leaf_reg

**Ожидаемое время:** 2-3 часа

---

### 4. 🔄 Optuna Hyperparameter Optimization (в процессе)

**Статус:** Запущен в фоновом режиме  
**Начало:** 2025-10-12 (текущее время)

**Процесс:**
1. Загрузка датасета с 84 динамическими фичами
2. Split: 60% train, 20% validation, 20% test
3. Optuna optimization:
   - XGBoost: 50 trials
   - LightGBM: 50 trials
   - CatBoost: 50 trials
4. Обучение финальных моделей на train+val с лучшими параметрами
5. Ensemble (Voting + Stacking)
6. Сравнение всех 5 моделей
7. Выбор лучшей по ROC AUC
8. Сохранение модели и метаданных

**Output файлы:**
- `artifacts/ensemble_<best_model>_<timestamp>.pkl` - лучшая модель
- `artifacts/ensemble_metadata_<timestamp>.json` - метрики и параметры

---

## 📊 Ожидаемые результаты

### Минимальные (реалистичные)
- ROC AUC >0.55 (улучшение с 0.4848)
- Accuracy >0.52 (улучшение с 0.4789)
- Sharpe Ratio >0.0 (хотя бы не убыточная модель)

### Целевые (хорошие)
- ROC AUC >0.60
- Accuracy >0.55
- Sharpe Ratio >1.0
- Total Return >3%
- Win Rate >50%
- Profit Factor >1.2

### Идеальные (отличные)
- ROC AUC >0.65
- Accuracy >0.58
- Sharpe Ratio >1.5
- Total Return >5%
- Win Rate >53%
- Profit Factor >1.5
- Max Drawdown <10%

---

## 🔍 Анализ изменений

### Почему убрали статичные фичи?

**Проблема:**
```python
# On-chain/Macro/Social вызываются ОДИН РАЗ для всего датасета:
onchain_feats = get_onchain_features(asset)  # Одно значение
for key, value in onchain_feats.items():
    df[key] = value  # Все строки получают одинаковое значение!
```

**Результат:**
- Нет вариативности во времени
- Модель не может научиться паттернам (всё одинаково)
- Шум вместо сигнала

**Решение:**
Убрать статичные фичи → оставить только динамические (изменяются во времени)

### Почему увеличили N_TRIALS?

**PHASE 1:** 30 trials (по 10 на модель) - быстрый тест  
**PHASE 2:** 150 trials (по 50 на модель) - серьезная оптимизация

**Ожидаемый эффект:**
- Более тщательный поиск оптимальных гиперпараметров
- Лучшая конвергенция Optuna (TPE sampler требует больше trials)
- Снижение overfitting через регуляризацию

---

## 📁 Измененные файлы

### Обновленные файлы (3)
1. **src/features.py**
   - Закомментированы блоки on-chain/macro/social (строки 269-322)
   - Закомментированы соответствующие feature_cols (строки 418-437)
   - Обновлены print-сообщения
   - Изменения: ~60 строк

2. **scripts/train_ensemble_optimized.py**
   - Исправлена Unicode ошибка (строка 167)
   - N_TRIALS: 30 → 150
   - TIMEOUT: 1800 → 7200
   - Добавлено подавление warnings
   - Изменения: ~10 строк

3. **docs/MODEL_IMPROVEMENT_PHASE2.md** (этот файл)
   - Новая документация для PHASE 2

---

## 🚀 Следующие шаги (после Optuna)

### 1. Проверка результатов Optuna
- Прочитать `artifacts/ensemble_metadata_<timestamp>.json`
- Проверить лучшую модель и метрики
- Сравнить AUC с baseline (0.4848)

### 2. Backtest улучшенной модели
```bash
python scripts/backtest_improved_model.py
```
- Загрузить обученную модель
- Простой backtest на test set
- Метрики: Sharpe, Return, Win Rate, Profit Factor, Max DD

### 3. Walk-Forward Validation
```bash
python scripts/walk_forward_validation.py
```
- Проверка стабильности модели на разных временных окнах
- Train window: 20 дней
- Test window: 5 дней
- Step: 5 дней

### 4. Анализ feature importance
- Какие фичи наиболее важны?
- Можно ли убрать еще несколько фичей?

### 5. Threshold optimization
- Не использовать 0.5 как порог для BUY
- Grid search: 0.45 - 0.65
- Оптимизация по Sharpe Ratio

---

## 📝 Команды для проверки прогресса

### Проверить статус Optuna (пока работает)
```powershell
# Посмотреть последние строки output
Get-Content artifacts\ensemble_metadata_*.json | Sort-Object -Descending | Select-Object -First 1
```

### После завершения Optuna
```bash
# Backtest
python scripts/backtest_improved_model.py

# Walk-Forward Validation
python scripts/walk_forward_validation.py

# Проверить метрики
cat artifacts/ensemble_metadata_<timestamp>.json
```

---

## ⏱ Временные оценки

| Задача | Время |
|--------|-------|
| ✅ Unicode fix | 2 минуты |
| ✅ Feature Selection | 10 минут |
| ✅ Optuna config update | 5 минут |
| 🔄 Optuna optimization | 2-3 часа (в процессе) |
| ⏳ Результаты анализа | 15 минут |
| ⏳ Backtest | 10 минут |
| ⏳ Walk-Forward | 30 минут |
| ⏳ Документация | 20 минут |
| ⏳ Коммит | 5 минут |
| **ИТОГО** | **~4 часа** |

---

## 🎯 Критерии успеха PHASE 2

### Минимальные (достаточно для продолжения)
- [ ] ROC AUC >0.55 (improvement от 0.4848)
- [ ] Sharpe Ratio >0.0 (хотя бы break-even)
- [ ] Модель обучена без ошибок

### Целевые (хорошо)
- [ ] ROC AUC >0.60
- [ ] Sharpe Ratio >1.0
- [ ] Total Return >3%
- [ ] Win Rate >50%

### Идеальные (отлично)
- [ ] ROC AUC >0.65
- [ ] Sharpe Ratio >1.5
- [ ] Total Return >5%
- [ ] Profit Factor >1.5
- [ ] Max Drawdown <10%

---

## 📚 Связанные файлы

- `docs/MODEL_IMPROVEMENT_PHASE1.md` - предыдущая фаза
- `ИТОГИ_ФАЗА1_MODEL_IMPROVEMENT.md` - итоги PHASE 1
- `src/features.py` - feature engineering
- `src/ensemble.py` - ensemble models
- `scripts/train_ensemble_optimized.py` - Optuna training
- `scripts/backtest_improved_model.py` - backtesting
- `scripts/walk_forward_validation.py` - validation

---

## 🔄 История изменений

### 2025-10-12 Evening
- ✅ Исправлена Unicode ошибка
- ✅ Feature Selection: убрано 28 статичных фичей (112 → 84)
- ✅ Optuna config: N_TRIALS 30 → 150, TIMEOUT 1800 → 7200
- 🔄 Запущен Optuna optimization (2-3 часа)
- ✅ Создана документация PHASE 2

---

**Статус:** 🔄 Optuna optimization в процессе  
**Следующий шаг:** Ожидание завершения Optuna → Анализ результатов → Backtest

---

**Последнее обновление:** 2025-10-12  
**Автор:** AI Assistant (Claude Sonnet 4.5)

