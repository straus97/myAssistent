# 🔧 Model Improvement PHASE 3: Cross-Validation для исправления Overfitting

**Дата:** 2025-10-12 (вечер)  
**Статус:** Скрипты готовы, ожидание запуска  
**Цель:** Исправить overfitting, обнаруженный в PHASE 2

---

## 🚨 ПРОБЛЕМА PHASE 2

### Overfitting Симптомы

| Метрика | Validation | Test | Проблема |
|---------|-----------|------|----------|
| **ROC AUC** | 0.6538 | 0.4829 | Test хуже случайного (0.5)! |
| **Improvement** | +35% | -3.4% | Validation показывает успех, Test - провал |

### Причина

Optuna оптимизировал гиперпараметры **под validation set**, что привело к:
1. Модель "запомнила" validation patterns
2. Не обобщается на новые данные (test set)
3. Классический пример overfitting

---

## ✅ РЕШЕНИЕ PHASE 3

### 1. TimeSeriesSplit (5-fold CV)

Вместо **single validation split (60/20/20)**, используем **5-fold TimeSeriesSplit**:

```
Fold 1:  Train [0:800] → Val [800:1000]
Fold 2:  Train [0:1000] → Val [1000:1200]
Fold 3:  Train [0:1200] → Val [1200:1400]
Fold 4:  Train [0:1400] → Val [1400:1600]
Fold 5:  Train [0:1600] → Val [1600:1800]

Test [1800:2129] — НЕТРОНУТ!
```

**Преимущества:**
- Модель оптимизируется на 5 разных временных окнах
- Нет единого validation set для переобучения
- Более реалистичная оценка обобщающей способности

---

### 2. Увеличенная Регуляризация

**XGBoost (новые параметры):**
```python
{
    "max_depth": 3-7,  # Было: 4-10
    "min_child_weight": 1-10,  # Новый параметр!
    "reg_alpha": 0.0-10.0,  # L1 регуляризация (было: 0.0-1.0)
    "reg_lambda": 1.0-10.0,  # L2 регуляризация (было: 1.0-5.0)
}
```

**LightGBM (новые параметры):**
```python
{
    "max_depth": 3-7,
    "min_child_samples": 10-50,  # Было: 5-20
    "reg_alpha": 0.0-10.0,
    "reg_lambda": 1.0-10.0,
}
```

**CatBoost (новые параметры):**
```python
{
    "depth": 3-7,
    "l2_leaf_reg": 1.0-10.0,  # Было: 1.0-5.0
    "random_strength": 0.0-2.0,  # Новый параметр!
}
```

**Эффект:**
- Более простые деревья (меньше max_depth)
- Больше данных для создания узлов (min_child_weight, min_child_samples)
- Сильная L1/L2 регуляризация

---

### 3. Aggregation Best Params

После 5 folds, усредняем параметры:

```python
def aggregate_params(params_list):
    for key in all_keys:
        if numeric:
            aggregated[key] = np.mean(values)  # Среднее
        else:
            aggregated[key] = Counter(values).most_common(1)[0][0]  # Мода
    return aggregated
```

**Эффект:** Получаем усредненные параметры, которые работают на всех фолдах.

---

## 📊 КРИТЕРИИ УСПЕХА

### Минимальный успех ✅
- [ ] Test AUC >0.55 (improvement с 0.4829)
- [ ] Test AUC > Validation AUC (нет overfitting!)
- [ ] Stable metrics на всех 5 CV folds (std <0.05)

### Целевой успех 🎯
- [ ] Test AUC >0.60
- [ ] Sharpe Ratio >1.0 (на backtest)
- [ ] Total Return >3% (на backtest)

### Идеальный успех 🏆
- [ ] Test AUC >0.65
- [ ] Sharpe Ratio >1.5
- [ ] Total Return >5%
- [ ] Ensemble превосходит single models

---

## 🛠 РЕАЛИЗАЦИЯ

### Новые файлы

1. **scripts/train_ensemble_cross_validation.py**
   - Загрузка датасета (84 фичи)
   - Train/Test split (80/20)
   - TimeSeriesSplit (5 folds) на train set
   - Optuna optimization на каждом fold (30 trials × 3 models)
   - Aggregation best params
   - Training final models на full train set
   - Evaluation на test set
   - Comparison с PHASE 2

2. **src/ensemble.py (обновлен)**
   - `optimize_xgboost_cv()` - Optuna с увеличенной регуляризацией
   - `optimize_lightgbm_cv()` - Аналогично для LightGBM
   - `optimize_catboost_cv()` - Аналогично для CatBoost
   - `train_voting_ensemble()` - VotingClassifier (sklearn)
   - `train_stacking_ensemble()` - StackingClassifier (sklearn)
   - `evaluate_ensemble()` - Metrics calculation

---

## 🚀 ЗАПУСК

```bash
# Активировать venv
.\.venv\Scripts\activate

# Запустить PHASE 3
python scripts\train_ensemble_cross_validation.py

# Ожидаемое время: ~1 час
# (5 folds × 3 models × 30 trials × ~40 sec/trial)
```

**Output:**
- `artifacts/ensemble_<model>_cv_<timestamp>.pkl` - лучшая модель
- `artifacts/ensemble_metadata_cv_<timestamp>.json` - метрики и параметры

---

## 📈 ОЖИДАЕМЫЕ РЕЗУЛЬТАТЫ

### Сценарий 1: SUCCESS (Test AUC >0.55)

```
PHASE 2 (Single Val):  Test AUC = 0.4829
PHASE 3 (Cross-Val):   Test AUC = 0.5800 (+20% improvement)

[SUCCESS] Overfitting fixed!

[NEXT STEPS]
1. Backtest с новой моделью
2. Paper trading monitoring
3. (Optional) Threshold optimization
```

### Сценарий 2: PARTIAL SUCCESS (Test AUC 0.50-0.55)

```
PHASE 2 (Single Val):  Test AUC = 0.4829
PHASE 3 (Cross-Val):   Test AUC = 0.5200 (+7.7% improvement)

[PARTIAL SUCCESS] Improvement detected, but more work needed

[NEXT STEPS]
1. Увеличить N_SPLITS (10-fold CV)
2. Загрузить больше исторических данных (6+ месяцев)
3. Feature engineering (добавить новые динамические фичи)
```

### Сценарий 3: FAILURE (Test AUC <0.50)

```
PHASE 2 (Single Val):  Test AUC = 0.4829
PHASE 3 (Cross-Val):   Test AUC = 0.4900 (+1.5% improvement)

[WARNING] No significant improvement

[NEXT STEPS]
1. Увеличить датасет (>10,000 samples)
2. Попробовать другие horizon_steps (12h, 24h)
3. Рассмотреть RL-подход вместо supervised learning
4. Альтернатива: простая модель (Logistic Regression)
```

---

## 🔍 АНАЛИЗ ПОСЛЕ ЗАПУСКА

### Вопросы для проверки

1. **Есть ли overfitting?**
   - Validation AUC >> Test AUC → ДА
   - Validation AUC ≈ Test AUC → НЕТ

2. **Stable ли метрики на CV folds?**
   - std(AUC) <0.05 → Стабильно
   - std(AUC) >0.10 → Нестабильно (проблема с данными)

3. **Помогла ли регуляризация?**
   - Сравнить PHASE 2 params vs PHASE 3 params
   - Проверить feature importance (топ-20 фич)

---

## 📚 LESSONS LEARNED

### Что пошло не так в PHASE 2?

1. **Single Validation Split**
   - Optuna оптимизировал под один фолд
   - Validation set стал "частью обучения"

2. **Слишком сложная модель**
   - max_depth=10 → overfitting
   - min_child_weight=1 → маленькие узлы
   - reg_lambda=1.0-5.0 → недостаточная регуляризация

3. **Нет проверки на overfitting**
   - Validation AUC выглядел отлично (0.6538)
   - Test AUC показал реальность (0.4829)

### Что исправили в PHASE 3?

1. ✅ **TimeSeriesSplit (5-fold CV)**
2. ✅ **Увеличенная регуляризация**
3. ✅ **Более простые модели** (меньше max_depth)
4. ✅ **Aggregation params** (усреднение по фолдам)

---

## 🎯 КРИТИЧЕСКИЕ МЕТРИКИ

| Метрика | PHASE 2 | PHASE 3 (Цель) |
|---------|---------|----------------|
| Test AUC | 0.4829 | >0.55 (минимум), >0.60 (идеал) |
| Validation AUC | 0.6538 | <0.65 (не должна расти) |
| Val-Test Gap | +0.1709 | <0.05 (нет overfitting!) |
| Sharpe (Backtest) | -1.98 | >1.0 |
| Total Return | -2.56% | >3% |

---

## 📝 ИТОГИ

- **PHASE 2:** Feature Selection + Optuna → overfitting обнаружен
- **PHASE 3:** Cross-Validation + регуляризация → ожидается исправление
- **Время:** ~1 час вычислений
- **Риск:** Если не поможет, нужно пересматривать подход (RL, больше данных, другие фичи)

---

**Последнее обновление:** 2025-10-12 вечер  
**Автор:** AI Assistant (Claude Sonnet 4.5)  
**Статус:** Готов к запуску

