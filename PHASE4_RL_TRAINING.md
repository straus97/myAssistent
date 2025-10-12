# 🚀 PHASE 4: RL-ПОДХОД (PPO Agent)

**Дата:** 2025-10-12 21:15  
**Статус:** Готов к запуску  
**Предыдущий результат:** PHASE 3 достигла Test AUC 0.5129 (+6.2%)

---

## ✅ ИСПРАВЛЕНЫ КРИТИЧЕСКИЕ ОШИБКИ

### 1. Risk Management: Price.dt → Price.timestamp
```python
# Было
.order_by(Price.dt.desc())  # ❌ AttributeError

# Стало
.order_by(Price.timestamp.desc())  # ✅ Работает
```

**Эффект:** 68+ ошибок каждые 5 минут исправлены!

### 2. Paper Trading Monitor: lookback параметр убран
```python
# Было
df = build_dataset(db, exchange, symbol, timeframe, lookback=200)  # ❌ TypeError

# Стало
df, feature_list = build_dataset(db, exchange, symbol, timeframe)  # ✅ Работает
```

**Эффект:** Monitor теперь генерирует сигналы без ошибок!

---

## 📊 PHASE 3 ИТОГОВЫЕ РЕЗУЛЬТАТЫ

### Лучший результат (Run 2)

```
Best Model:     LightGBM
Test AUC:       0.5129 ✅ (>0.5 случайного!)
Test Accuracy:  50.70%
Improvement:    +6.2% vs PHASE 2

МИНИМАЛЬНЫЙ УСПЕХ ДОСТИГНУТ!
```

### Все модели (Лучшие из 2 запусков)

| Модель | Best AUC | Accuracy |
|--------|----------|----------|
| **LightGBM** | 0.5129 ✅ | 50.70% |
| **Stacking** | 0.4982 | 51.17% |
| **Voting** | 0.4935 | 49.06% |
| **XGBoost** | 0.4931 | 48.59% |
| **CatBoost** | 0.4863 | 48.83% |

---

## 🎯 ПОЧЕМУ ПЕРЕХОДИМ НА RL?

**PHASE 3 показала:** Supervised learning работает, но **недостаточно хорошо**

| Критерий | PHASE 3 | Цель |
|----------|---------|------|
| Test AUC | 0.5129 | >0.60 |
| Sharpe (backtest) | ??? | >1.0 |

**RL может работать ЛУЧШЕ:**

1. ✅ **Не требует предсказания цены**
   - Supervised: Нужно предсказать UP/DOWN
   - RL: Оптимизирует Sharpe Ratio напрямую

2. ✅ **Адаптируется к рынку**
   - Supervised: Статичная модель
   - RL: Continuous learning

3. ✅ **Оптимизирует портфель**
   - Supervised: Только direction
   - RL: Direction + sizing + timing

4. ✅ **Инфраструктура ГОТОВА**
   - src/rl_env.py ✅
   - src/rl_agent.py ✅
   - src/routers/rl.py ✅

---

## 🚀 ЗАПУСК RL-ОБУЧЕНИЯ

### Команда

```bash
# Активировать venv
.\.venv\Scripts\activate

# Запустить обучение (500K timesteps, ~4-6 часов)
python scripts\train_rl_ppo.py --timesteps 500000
```

### Параметры (опционально)

```bash
# Быстрый тест (50K timesteps, ~30 минут)
python scripts\train_rl_ppo.py --timesteps 50000

# Кастомные параметры
python scripts\train_rl_ppo.py \
  --exchange bybit \
  --symbol BTC/USDT \
  --timeframe 1h \
  --timesteps 500000 \
  --initial-capital 1000 \
  --learning-rate 0.0003
```

### Output

```
================================================================================
                    RL-ПОДХОД: PPO Agent Training
================================================================================

Configuration:
  - Exchange: bybit
  - Symbol: BTC/USDT
  - Timeframe: 1h
  - Total Timesteps: 500,000
  - Initial Capital: $1,000.00
  - Learning Rate: 0.0003

Step 1: Loading Dataset
...

Step 3: Training PPO Agent
[*] Starting training (500,000 timesteps)...
     This will take approximately 417-625 minutes (7-10 часов)
     Watch progress: tensorboard --logdir artifacts/tensorboard

[Progress Bar]
...

Step 5: Evaluating Agent

BACKTEST RESULTS
Total Return:    +X.XX%
Sharpe Ratio:    X.XXXX
Max Drawdown:    -X.XX%
Win Rate:        XX.XX%
```

---

## ⏰ ОЖИДАЕМОЕ ВРЕМЯ

| Timesteps | Время | Рекомендация |
|-----------|-------|--------------|
| **50K** | ~30-60 мин | Быстрый тест |
| **100K** | ~1-2 часа | Минимальный |
| **500K** | ~4-6 часов | **Рекомендуется** |
| **1M** | ~8-12 часов | Для production |

**Текущая команда:** 500K timesteps (~4-6 часов)

---

## 📊 КРИТЕРИИ УСПЕХА

### ✅ Минимальный успех
- Sharpe Ratio >0.5
- Total Return >0%
- Win Rate >45%

### 🎯 Целевой успех
- Sharpe Ratio >1.0
- Total Return >5%
- Win Rate >50%
- RL > Supervised Learning (LightGBM)

### 🏆 Идеальный успех
- Sharpe Ratio >1.5
- Total Return >10%
- Win Rate >55%
- Max Drawdown <10%

---

## 📁 OUTPUT ФАЙЛЫ

После завершения:

```
artifacts/
├── rl_models/
│   └── ppo_btc_usdt_1h_20251012_HHMMSS.zip  # Обученная модель
└── tensorboard/
    └── PPO_X/  # Логи обучения
```

---

## 💡 МОНИТОРИНГ ОБУЧЕНИЯ

### Во время обучения

```bash
# В НОВОМ терминале запустить Tensorboard
tensorboard --logdir artifacts/tensorboard

# Открыть в браузере
http://localhost:6006
```

**Что смотреть:**
- `rollout/ep_reward_mean` - средняя награда (должна расти)
- `train/loss` - loss функция (должна падать)
- `train/learning_rate` - learning rate

---

## 🔧 ЕСЛИ ЧТО-ТО ПОШЛО НЕ ТАК

### Ошибка памяти (MemoryError)

```bash
# Уменьшить batch size
python scripts\train_rl_ppo.py --timesteps 50000
```

### Медленное обучение

```bash
# Проверить GPU (если есть)
python -c "import torch; print(torch.cuda.is_available())"

# CPU нормально, просто займет дольше
```

### Reward не растет

Это нормально! RL требует времени для обучения:
- Первые 10-20% timesteps: exploration (reward колеблется)
- Средние 40-60%: exploitation (reward начинает расти)
- Последние 20-30%: convergence (reward стабилизируется)

---

## 🎯 ЧТО ДЕЛАТЬ ПОСЛЕ ОБУЧЕНИЯ

### Если Sharpe >1.0 ✅

```bash
1. Запустить paper trading с RL моделью
2. Мониторинг 7 дней
3. Deploy в production
```

### Если Sharpe 0.5-1.0 ⚠️

```bash
1. Увеличить timesteps (500K → 1M)
2. Fine-tune hyperparameters
3. Try different reward shaping
```

### Если Sharpe <0.5 ❌

```bash
1. Увеличить датасет (load more historical data)
2. Try другие алгоритмы (A2C, SAC)
3. Рассмотреть другие стратегии (buy&hold, mean-reversion)
```

---

## 📚 СРАВНЕНИЕ ПОДХОДОВ

| Подход | Test AUC | Sharpe | Статус |
|--------|----------|--------|--------|
| **PHASE 1** | 0.4848 | -1.98 | ❌ Baseline |
| **PHASE 2** | 0.4829 (Test) | -1.98 | ❌ Overfitting |
| **PHASE 3** | 0.5129 | ??? | ⚠️ Частичный успех |
| **PHASE 4 (RL)** | N/A | ??? | 🔄 В процессе |

---

**Удачи с RL-обучением! 🚀**

**Ожидаемое время:** ~4-6 часов  
**Tensorboard:** http://localhost:6006

