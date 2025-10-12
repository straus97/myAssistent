# 🚀 Запуск и Мониторинг PHASE 3

## ✅ Что уже сделано

1. ✅ **Зависимости установлены** (optuna, lightgbm, catboost, etc.)
2. ✅ **Скрипт запущен в фоне**: `scripts\train_ensemble_cross_validation.py`
3. ✅ **Ожидаемое время**: ~1 час

---

## 📊 Как Следить за Прогрессом

### Вариант 1: Запустить в новом терминале (рекомендуется)

Если хочешь видеть live output:

```bash
# Открыть новый PowerShell/CMD
cd C:\AI\myAssistent
.\.venv\Scripts\activate
python scripts\train_ensemble_cross_validation.py
```

**Output будет показывать:**
```
================================================================================
                    PHASE 3: Cross-Validation + Walk-Forward
================================================================================

Configuration:
  - TimeSeriesSplit: 5 folds
  - Optuna Trials per Model: 30
  - Timeout: 3600s (60 minutes)
  ...

Fold 1/5
  Train: 1277 samples
  Val:   426 samples

[Fold 1] Optimizing XGBoost (30 trials)...
[Fold 1] XGBoost best params: {...}

[Fold 1] Optimizing LightGBM (30 trials)...
...
```

---

### Вариант 2: Проверить файлы артефактов

```bash
# Каждые 5-10 минут проверяй
dir artifacts\ensemble_*_cv_*.pkl
dir artifacts\ensemble_metadata_cv_*.json
```

**Если файлы появились** → обучение завершено!

---

### Вариант 3: Проверить процессы

```bash
# Проверить, что Python процесс еще работает
tasklist | findstr python
```

Если видишь несколько `python.exe` → скрипт работает.

---

## 🎯 Что Ожидать

### Этапы выполнения

| Этап | Время | Описание |
|------|-------|----------|
| **1. Dataset Loading** | 10-30 сек | Загрузка 2129 rows × 84 features |
| **2. Fold 1 (XGB)** | 5-10 мин | Optuna 30 trials |
| **3. Fold 1 (LGB)** | 5-10 мин | Optuna 30 trials |
| **4. Fold 1 (CAT)** | 5-10 мин | Optuna 30 trials |
| **5. Folds 2-5** | 40-50 мин | Повторение для остальных фолдов |
| **6. Final Training** | 2-5 мин | Обучение на полном train set |
| **7. Evaluation** | 10-30 сек | Оценка на test set |

**Итого:** ~55-75 минут (в среднем 60 минут)

---

## 📁 Output Файлы

После завершения появятся:

```
artifacts/
├── ensemble_<model>_cv_20251012_HHMMSS.pkl    # Лучшая модель
└── ensemble_metadata_cv_20251012_HHMMSS.json  # Метрики
```

**Пример metadata:**
```json
{
  "timestamp": "20251012_220530",
  "phase": 3,
  "method": "cross_validation",
  "n_splits": 5,
  "best_model": "xgboost",
  "test_auc": 0.5834,
  "phase2_test_auc": 0.4829,
  "improvement_pct": 20.8,
  "all_results": {
    "xgboost": {"test_auc": 0.5834, "test_accuracy": 0.5612},
    "lightgbm": {"test_auc": 0.5721, "test_accuracy": 0.5534},
    ...
  }
}
```

---

## 🎉 Критерии Успеха

### ✅ Минимальный успех
- `test_auc > 0.55` (улучшение с 0.4829)
- `improvement_pct > 0`

### 🎯 Целевой успех
- `test_auc > 0.60`
- `improvement_pct > 20%`

### 🏆 Идеальный успех
- `test_auc > 0.65`
- `improvement_pct > 35%`

---

## 🔧 Если Что-то Пошло Не Так

### Ошибка: "ModuleNotFoundError"

```bash
# Переустановить зависимости
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Скрипт завис

```bash
# Проверить процессы
tasklist | findstr python

# Убить процесс (если нужно)
taskkill /F /IM python.exe
```

### Нехватка памяти

Если видишь ошибку `MemoryError`:

1. Закрыть другие приложения
2. Уменьшить `N_TRIALS` в скрипте (30 → 10)
3. Запустить заново

---

## 📊 Сравнение Результатов

После завершения:

```bash
# Прочитать метрики
python -c "import json; print(json.dumps(json.load(open('artifacts/ensemble_metadata_cv_<timestamp>.json')), indent=2))"
```

**Или вручную:**

```json
PHASE 2 (Single Validation):
- Test AUC: 0.4829
- Val AUC: 0.6538 (overfitting!)

PHASE 3 (Cross-Validation):
- Test AUC: ??? (цель >0.55)
- Val AUC: ??? (должен быть близок к Test)
```

---

## 🚀 Следующие Шаги

### Если Test AUC >0.55 ✅

```bash
# 1. Backtest с новой моделью
python scripts/backtest_improved_model.py

# 2. Paper Trading с новой моделью
# (обновить paper_state.json с новым model_path)

# 3. (Опционально) Threshold optimization
```

### Если Test AUC 0.50-0.55 ⚠️

Частичный успех, нужно:
- Увеличить N_SPLITS (5 → 10 folds)
- Загрузить больше исторических данных
- Feature engineering (новые фичи)

### Если Test AUC <0.50 ❌

Провал, рассмотреть:
- Увеличение датасета (>10,000 samples)
- Другие horizon_steps (12h, 24h)
- **RL-подход** вместо supervised learning

---

## 💡 Полезные Команды

```bash
# Проверить статус
tasklist | findstr python

# Проверить файлы
dir artifacts\ensemble_*_cv_*.*

# Убить все Python процессы (осторожно!)
taskkill /F /IM python.exe

# Запустить заново (если нужно)
python scripts\train_ensemble_cross_validation.py
```

---

**Удачи с обучением PHASE 3! 🚀**

**Estimated completion:** ~60 минут от запуска  
**Current time:** Проверь, когда запустил скрипт

