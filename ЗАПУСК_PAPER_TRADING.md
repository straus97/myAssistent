# 🚀 Paper Trading - Запуск и Мониторинг

**Статус:** ✅ Paper Monitor ЗАПУЩЕН!  
**Дата запуска:** 2025-10-12  

---

## ✅ Текущий статус

```
Monitor: ВКЛЮЧЕН ✅
Equity: $13,530.04
Позиций: 76
Обновлений: 1
Сигналов: 0 (нужна модель для новых)
Errors: 0

Risk Management:
- Stop-Loss: -2% ✅
- Take-Profit: +5% ✅
- Max Exposure: 50% ⚠️ (текущий 93.7%)
```

**Предупреждение:** У вас высокий exposure (93.7%) из-за 76 старых позиций. Новые сделки будут заблокированы до снижения exposure.

---

## 📊 Команды для мониторинга

### Получить API_KEY из .env (PowerShell)
```powershell
$env:API_KEY = (Get-Content .env | Select-String "^API_KEY=" | ForEach-Object { $_ -replace "API_KEY=","" })
```

### 1. Проверить статус Paper Monitor
```powershell
curl -X GET "http://localhost:8000/paper-monitor/status" -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json
```

**Что смотреть:**
- `enabled`: true (монитор работает)
- `last_update`: время последнего обновления
- `total_signals`: количество сгенерированных сигналов
- `equity`: текущий капитал
- `positions_count`: открытых позиций

---

### 2. Посмотреть equity за 24 часа
```powershell
curl -X GET "http://localhost:8000/paper-monitor/equity/chart?hours=24" -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 5
```

**Данные для графика:**
- `timestamps[]`: временные метки
- `equity[]`: капитал в каждый момент
- `pnl[]`: PnL в USDT
- `pnl_pct[]`: PnL в процентах

---

### 3. Сводка по периодам
```powershell
curl -X GET "http://localhost:8000/paper-monitor/equity/summary" -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 5
```

**Показывает изменения за:**
- 1h, 24h, 7d, 30d

---

### 4. Проверить Risk Management
```powershell
curl -X GET "http://localhost:8000/risk-management/status" -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 5
```

**Что смотреть:**
- `current_exposure`: текущий exposure (% капитала в позициях)
- `active_trailing_stops`: количество активных trailing stops

---

### 5. Получить рекомендации по позициям
```powershell
curl -X GET "http://localhost:8000/risk-management/recommendations" -H "X-API-Key: $env:API_KEY" | ConvertFrom-Json | ConvertTo-Json -Depth 5
```

**Показывает для каждой позиции:**
- Текущую цену и PnL
- Предупреждения (если триггерится SL/TP)
- Рекомендации по действиям

---

### 6. Запустить ручное обновление
```powershell
curl -X POST "http://localhost:8000/paper-monitor/update" -H "X-API-Key: $env:API_KEY"
```

Используйте если хотите обновить прямо сейчас (не дожидаясь 15 минут).

---

### 7. Проверить здоровье системы
```powershell
curl -X GET "http://localhost:8000/health" | ConvertFrom-Json | ConvertTo-Json
```

**Проверяет:**
- Database connection
- Scheduler status
- Model availability
- Sentry status

---

## 🎯 Что происходит автоматически

### Каждые 15 минут (Paper Monitor):
1. Обновляются цены для BTC/USDT
2. Генерируются сигналы (если есть модель)
3. Обновляется equity
4. Сохраняется snapshot для графика
5. Отправляются Telegram уведомления (если есть сигналы)

### Каждые 5 минут (Risk Management):
1. Проверяются все 76 открытых позиций
2. Закрываются позиции при:
   - Stop-Loss: убыток >= -2%
   - Take-Profit: прибыль >= +5%
   - Position Age: старше 72 часов
3. Отправляются Telegram уведомления о закрытиях

### Каждые 5 минут (Healthcheck):
1. Ping на healthchecks.io (если настроено)
2. Проверка что система работает

---

## 📈 Как мониторить

### Вариант 1: Через Dashboard (рекомендуется)

```bash
# В новом терминале
cd frontend
npm run dev

# Открыть в браузере
http://localhost:3000
```

**Dashboard покажет:**
- Real-time equity chart
- Список позиций
- Последние сигналы
- Метрики модели

---

### Вариант 2: Через API (скрипт)

Создайте файл `check_status.ps1`:

```powershell
$API_KEY = (Get-Content .env | Select-String "^API_KEY=" | ForEach-Object { $_ -replace "API_KEY=","" })

Write-Host "`n=== PAPER MONITOR STATUS ===" -ForegroundColor Green
$status = curl -s -X GET "http://localhost:8000/paper-monitor/status" -H "X-API-Key: $API_KEY" | ConvertFrom-Json
Write-Host "Enabled: $($status.enabled)"
Write-Host "Last Update: $($status.last_update)"
Write-Host "Total Updates: $($status.stats.total_updates)"
Write-Host "Total Signals: $($status.stats.total_signals)"
Write-Host "Equity: `$$($status.equity.equity)"
Write-Host "Positions: $($status.positions_count)"

Write-Host "`n=== RISK MANAGEMENT ===" -ForegroundColor Yellow
$risk = curl -s -X GET "http://localhost:8000/risk-management/exposure" -H "X-API-Key: $API_KEY" | ConvertFrom-Json
Write-Host "Exposure: $([math]::Round($risk.exposure_pct, 2))%"
Write-Host "Status: $($risk.status)"
if ($risk.message) {
    Write-Host "Warning: $($risk.message)" -ForegroundColor Red
}
```

Запускать:
```powershell
.\check_status.ps1
```

---

### Вариант 3: Логи сервера

```bash
# Смотреть логи backend
tail -f logs/app.log

# Или в PowerShell
Get-Content logs\app.log -Wait -Tail 50
```

**Что искать:**
- `[scheduler] paper_monitor:` - обновления монитора
- `[scheduler] risk_checks:` - проверки рисков
- `[MONITOR] Generated signal` - новые сигналы
- `[RISK] Closed` - закрытые позиции

---

## 🔔 Telegram уведомления

Если настроен TELEGRAM_BOT_TOKEN, вы будете получать:

**От Paper Monitor:**
```
[PAPER TRADING] Новые сигналы!

Equity: $13,530.04 (+35.30%)
Позиций: 76

BTC/USDT: BUY @ $62,450.00
Probability: 67.5%
```

**От Risk Management:**
```
[RISK] STOP-LOSS
BTC/USDT: -2.15%
Entry: $62,000.00
Close: $60,670.00
Reason: Stop-Loss triggered
```

---

## 📊 Что смотреть в течение недели

### Ежедневно:
1. **Equity:**
   - Растёт или падает?
   - Стабильно или скачет?
   
2. **Количество позиций:**
   - Открываются новые? (нужна обученная модель)
   - Закрываются старые? (Risk Management работает)

3. **Exposure:**
   - Снижается с 93.7%?
   - Достигнет ли 50%?

### Каждые 3 дня:
1. **Сводка по периодам:**
   ```powershell
   curl -X GET "http://localhost:8000/paper-monitor/equity/summary" -H "X-API-Key: $env:API_KEY"
   ```

2. **Статистика:**
   - Total updates (должно расти)
   - Total signals (если есть модель)
   - Errors (должно быть 0)

---

## 🎯 Критерии успеха (7 дней)

| Метрика | Целевое значение | Как проверить |
|---------|------------------|---------------|
| **Equity** | Не падает | `/equity/summary` |
| **Updates** | ~672 (7×24×4) | `/status` → stats.total_updates |
| **Errors** | 0 | `/status` → stats.errors |
| **Exposure** | Снижается к 50% | `/risk-management/exposure` |
| **Closed positions** | 10+ | Логи Risk Management |

---

## 🛠️ Дополнительные команды

### Остановить Monitor (если нужно)
```powershell
curl -X POST "http://localhost:8000/paper-monitor/stop" -H "X-API-Key: $env:API_KEY"
```

### Настроить Monitor
```powershell
$config = @{
    enabled = $true
    update_interval_minutes = 15
    symbols = @("BTC/USDT", "ETH/USDT")
    auto_execute = $false
    notifications = $true
} | ConvertTo-Json

curl -X POST "http://localhost:8000/paper-monitor/config" `
    -H "X-API-Key: $env:API_KEY" `
    -H "Content-Type: application/json" `
    -d $config
```

### Включить Trailing Stop
```powershell
$risk_config = @{
    enabled = $true
    trailing_stop = @{
        enabled = $true
        activation_percentage = 0.03
        trail_percentage = 0.015
        notify = $true
    }
} | ConvertTo-Json

curl -X POST "http://localhost:8000/risk-management/config" `
    -H "X-API-Key: $env:API_KEY" `
    -H "Content-Type: application/json" `
    -d $risk_config
```

---

## ⚠️ Важные замечания

### 1. Exposure 93.7% - это нормально?

**Да, для текущей ситуации:**
- У вас 76 старых позиций из предыдущих сессий
- Risk Management будет постепенно закрывать их при SL/TP
- Новые позиции НЕ будут открываться пока exposure не снизится

**Что делать:**
- Ничего! Просто ждать
- Risk Management автоматически закроет позиции
- Через несколько дней exposure снизится

---

### 2. 0 новых сигналов - это проблема?

**Нет, это ожидаемо:**
- Для генерации сигналов нужна обученная модель
- В artifacts/models/ нет моделей (предупреждение из production_check)

**Что делать:**
```bash
# Обучить модель на свежих данных
POST /model/train
{
  "exchange": "bybit",
  "symbol": "BTC/USDT",
  "timeframe": "1h"
}

# Или через скрипт
python scripts/train_dynamic_features_only.py
```

После обучения Monitor начнёт генерировать новые сигналы!

---

### 3. Как часто проверять?

**Оптимально:**
- **1 раз в день:** Проверить equity и exposure
- **1 раз в 3 дня:** Посмотреть статистику и сводку
- **1 раз в неделю:** Проверить Risk Management actions

**Не нужно:**
- Проверять каждый час (система автоматическая!)
- Вмешиваться вручную (пусть работает сама)
- Паниковать при небольших колебаниях

---

## 📱 Мониторинг через Telegram

Если настроен `TELEGRAM_BOT_TOKEN`, вы автоматически получите:
- Уведомления о новых сигналах
- Уведомления о закрытии позиций (SL/TP)
- Предупреждения о проблемах

**Не нужно постоянно проверять API - Telegram всё покажет!**

---

## 🎯 План на неделю

### День 1 (сегодня):
- ✅ Paper Monitor запущен
- ✅ Risk Management активен
- ⏳ Обучить модель (опционально)

### День 3:
- Проверить equity summary
- Посмотреть сколько позиций закрылось
- Проверить exposure (должен снизиться)

### День 7:
- Полная проверка статистики
- Оценить результаты
- Решить продолжать или улучшать модель

---

## 🚀 Следующие шаги

### Если всё хорошо через 7 дней:
1. Продолжить paper trading ещё 3 недели (итого 30 дней)
2. Накопить достаточно статистики
3. Достичь целевых метрик (Return >10%, Sharpe >1.5)

### Если нужно улучшение:
1. Запустить Walk-Forward Validation
2. Улучшить модель (больше данных, фичей)
3. Перезапустить paper trading

---

## 📞 Полезные ссылки

**API Documentation:**
- http://localhost:8000/docs - Swagger UI

**Dashboards:**
- http://localhost:3000 - Next.js Frontend
- http://localhost:5000 - MLflow UI
- http://localhost:3001 - Grafana

**Документация:**
- `docs/PAPER_TRADING_REALTIME.md` - Полное руководство
- `docs/PRODUCTION_DEPLOYMENT.md` - Production guide
- `docs/FINAL_SUMMARY.md` - Итоговая сводка

---

**Paper Trading запущен! Наблюдайте и анализируйте! 📊**

