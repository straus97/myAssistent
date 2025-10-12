# ===================================
# Paper Trading - Проверка и Управление
# ===================================

$API_KEY = "4ac25807582dae9f9b91396d7ccd223ba796bfdb7077241a994bdeff874b4faf"
$BASE_URL = "http://127.0.0.1:8000"
$Headers = @{"X-API-Key" = $API_KEY}

function Show-Menu {
    Write-Host "`n==================================" -ForegroundColor Cyan
    Write-Host "  PAPER TRADING - УПРАВЛЕНИЕ" -ForegroundColor Cyan
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host "1. Статус Monitor"
    Write-Host "2. EMA Crossover сигнал (BTC/USDT)"
    Write-Host "3. Текущий Equity"
    Write-Host "4. Открытые позиции"
    Write-Host "5. Запустить Monitor"
    Write-Host "6. Остановить Monitor"
    Write-Host "7. Включить Auto-Execute"
    Write-Host "8. Выключить Auto-Execute"
    Write-Host "9. Ручное обновление"
    Write-Host "0. Выход"
    Write-Host "==================================" -ForegroundColor Cyan
}

function Get-MonitorStatus {
    Write-Host "`n[Статус Monitor]" -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri "$BASE_URL/paper-monitor/status" -Method GET -Headers $Headers -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    
    Write-Host "Включен: $($data.enabled)" -ForegroundColor $(if($data.enabled) {"Green"} else {"Red"})
    Write-Host "Auto-Execute: $($data.auto_execute)" -ForegroundColor $(if($data.auto_execute) {"Green"} else {"Yellow"})
    Write-Host "Последнее обновление: $($data.last_update)"
    Write-Host "Интервал: $($data.update_interval_minutes) минут"
    Write-Host "Символы: $($data.symbols -join ', ')"
    Write-Host "`nEquity:"
    Write-Host "  Cash: $$([math]::Round($data.equity.cash, 2))"
    Write-Host "  Positions: $$([math]::Round($data.equity.positions_value, 2))"
    Write-Host "  Total: $$([math]::Round($data.equity.equity, 2))" -ForegroundColor Green
    Write-Host "`nСтатистика:"
    Write-Host "  Обновлений: $($data.stats.total_updates)"
    Write-Host "  Сигналов: $($data.stats.total_signals)"
    Write-Host "  Открытых позиций: $($data.positions_count)"
}

function Get-EMASignal {
    Write-Host "`n[EMA Crossover Сигнал - BTC/USDT 1h]" -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri "$BASE_URL/simple_strategy/test_ema" -Method GET -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    
    $signalColor = switch($data.signal) {
        "BUY" { "Green" }
        "SELL" { "Red" }
        default { "Yellow" }
    }
    
    Write-Host "Сигнал: $($data.signal)" -ForegroundColor $signalColor
    Write-Host "Цена: $$($data.current_price)"
    Write-Host "Время: $($data.timestamp)"
    Write-Host "Стратегия: $($data.strategy)"
    Write-Host "`nДетали:"
    Write-Host "  Проанализировано баров: $($data.details.bars_analyzed)"
    Write-Host "  BUY сигналов: $($data.details.total_buy_signals)"
    Write-Host "  SELL сигналов: $($data.details.total_sell_signals)"
    Write-Host "  HOLD сигналов: $($data.details.total_hold_signals)"
}

function Get-Equity {
    Write-Host "`n[Текущий Equity]" -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri "$BASE_URL/paper-monitor/equity/summary" -Method GET -Headers $Headers -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    
    Write-Host "`n24 часа:"
    Write-Host "  Начало: $$([math]::Round($data.summary.'24h'.equity_start, 2))"
    Write-Host "  Конец: $$([math]::Round($data.summary.'24h'.equity_end, 2))"
    $change = $data.summary.'24h'.change_pct
    $changeColor = if($change -gt 0) {"Green"} else {"Red"}
    Write-Host "  Изменение: $([math]::Round($change, 2))%" -ForegroundColor $changeColor
}

function Get-Positions {
    Write-Host "`n[Открытые позиции]" -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri "$BASE_URL/trade/positions" -Method GET -Headers $Headers -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    
    $activePositions = $data.positions | Where-Object { $_.qty -gt 0 }
    Write-Host "Всего позиций: $($data.positions.Count)"
    Write-Host "Активных: $($activePositions.Count)" -ForegroundColor Green
    
    if ($activePositions.Count -gt 0) {
        Write-Host "`nТоп-10 активных позиций:"
        $activePositions | Select-Object -First 10 | ForEach-Object {
            Write-Host "  $($_.symbol) [$($_.exchange)]: $([math]::Round($_.qty, 4)) шт @ $$([math]::Round($_.avg_price, 2))"
        }
    }
}

function Start-Monitor {
    Write-Host "`n[Запуск Monitor]" -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri "$BASE_URL/paper-monitor/start" -Method POST -Headers $Headers -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    Write-Host "Статус: $($data.status)" -ForegroundColor Green
    Write-Host "Сообщение: $($data.message)"
}

function Stop-Monitor {
    Write-Host "`n[Остановка Monitor]" -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri "$BASE_URL/paper-monitor/stop" -Method POST -Headers $Headers -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    Write-Host "Статус: $($data.status)" -ForegroundColor Yellow
    Write-Host "Сообщение: $($data.message)"
}

function Enable-AutoExecute {
    Write-Host "`n[Включение Auto-Execute]" -ForegroundColor Yellow
    $body = @{
        enabled = $true
        update_interval_minutes = 15
        symbols = @("BTC/USDT")
        exchange = "bybit"
        timeframe = "1h"
        auto_execute = $true
        notifications = $true
    } | ConvertTo-Json
    
    $response = Invoke-WebRequest -Uri "$BASE_URL/paper-monitor/config" -Method POST -Headers $Headers -Body $body -ContentType "application/json" -UseBasicParsing
    Write-Host "Auto-Execute включен!" -ForegroundColor Green
}

function Disable-AutoExecute {
    Write-Host "`n[Выключение Auto-Execute]" -ForegroundColor Yellow
    $body = @{
        enabled = $true
        update_interval_minutes = 15
        symbols = @("BTC/USDT")
        exchange = "bybit"
        timeframe = "1h"
        auto_execute = $false
        notifications = $true
    } | ConvertTo-Json
    
    $response = Invoke-WebRequest -Uri "$BASE_URL/paper-monitor/config" -Method POST -Headers $Headers -Body $body -ContentType "application/json" -UseBasicParsing
    Write-Host "Auto-Execute выключен!" -ForegroundColor Yellow
}

function Manual-Update {
    Write-Host "`n[Ручное обновление]" -ForegroundColor Yellow
    $response = Invoke-WebRequest -Uri "$BASE_URL/paper-monitor/update" -Method POST -Headers $Headers -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    Write-Host "Статус: $($data.status)" -ForegroundColor Green
    Write-Host "Сообщение: $($data.message)"
}

# Основной цикл
do {
    Show-Menu
    $choice = Read-Host "`nВыберите действие"
    
    switch ($choice) {
        "1" { Get-MonitorStatus }
        "2" { Get-EMASignal }
        "3" { Get-Equity }
        "4" { Get-Positions }
        "5" { Start-Monitor }
        "6" { Stop-Monitor }
        "7" { Enable-AutoExecute }
        "8" { Disable-AutoExecute }
        "9" { Manual-Update }
        "0" { Write-Host "`nДо свидания!" -ForegroundColor Cyan; exit }
        default { Write-Host "`nНеверный выбор!" -ForegroundColor Red }
    }
    
    Read-Host "`nНажмите Enter для продолжения"
} while ($true)
