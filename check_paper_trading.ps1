# Скрипт для быстрой проверки статуса Paper Trading
# Использование: .\check_paper_trading.ps1

$ErrorActionPreference = "SilentlyContinue"

# Получаем API_KEY из .env
$API_KEY = (Get-Content .env | Select-String "^API_KEY=" | ForEach-Object { $_ -replace "API_KEY=","" }).ToString().Trim()

if (-not $API_KEY) {
    Write-Host "[ERROR] API_KEY не найден в .env" -ForegroundColor Red
    exit 1
}

$BASE_URL = "http://localhost:8000"
$HEADERS = @{
    "X-API-Key" = $API_KEY
}

function Format-Json($json) {
    return $json | ConvertFrom-Json | ConvertTo-Json -Depth 5
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  MyAssistent - Paper Trading Status" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. Paper Monitor Status
Write-Host "[1/4] Paper Monitor Status..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/paper-monitor/status" -Headers $HEADERS -Method Get
    Write-Host "  Enabled: " -NoNewline
    if ($response.enabled) { Write-Host "YES" -ForegroundColor Green } else { Write-Host "NO" -ForegroundColor Red }
    Write-Host "  Last Update: $($response.last_update)"
    Write-Host "  Total Updates: $($response.stats.total_updates)"
    Write-Host "  Total Signals: $($response.stats.total_signals)"
    Write-Host "  Errors: $($response.stats.errors)"
    Write-Host "  Equity: `$$([math]::Round($response.equity.equity, 2))" -ForegroundColor Green
    Write-Host "  Positions: $($response.positions_count)" -ForegroundColor Cyan
}
catch {
    Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

# 2. Risk Management Status
Write-Host "`n[2/4] Risk Management..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/risk-management/exposure" -Headers $HEADERS -Method Get
    Write-Host "  Exposure: $([math]::Round($response.exposure_pct, 1))%" -NoNewline
    if ($response.status -eq "OK") {
        Write-Host " [OK]" -ForegroundColor Green
    } else {
        Write-Host " [WARNING]" -ForegroundColor Yellow
        if ($response.message) {
            Write-Host "    $($response.message)" -ForegroundColor Yellow
        }
    }
    Write-Host "  Max Allowed: $($response.max_allowed_pct)%"
    Write-Host "  Equity: `$$([math]::Round($response.equity, 2))"
    Write-Host "  Positions Value: `$$([math]::Round($response.positions_value, 2))"
}
catch {
    Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

# 3. Health Check
Write-Host "`n[3/4] System Health..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/health" -Method Get
    Write-Host "  Status: $($response.status)" -NoNewline
    if ($response.status -eq "ok") {
        Write-Host " [OK]" -ForegroundColor Green
    } else {
        Write-Host " [DEGRADED]" -ForegroundColor Yellow
    }
    Write-Host "  Version: $($response.version)"
    Write-Host "  Services:"
    foreach ($service in $response.services.PSObject.Properties) {
        Write-Host "    $($service.Name): $($service.Value)"
    }
}
catch {
    Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

# 4. Recent Signals
Write-Host "`n[4/4] Recent Signals..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/signals/recent?limit=5" -Method Get
    $signals = $response.data
    if ($signals.Count -gt 0) {
        Write-Host "  Found $($signals.Count) recent signals:"
        foreach ($sig in $signals | Select-Object -First 3) {
            Write-Host "    $($sig.symbol) - $($sig.signal) @ `$$($sig.price) ($($sig.created_at))"
        }
    } else {
        Write-Host "  No recent signals"
    }
}
catch {
    Write-Host "  ERROR: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Check complete!" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Quick links:" -ForegroundColor Gray
Write-Host "  Swagger UI:  http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "  Dashboard:   http://localhost:3000" -ForegroundColor Gray
Write-Host "  MLflow:      http://localhost:5000" -ForegroundColor Gray
Write-Host "  Grafana:     http://localhost:3001" -ForegroundColor Gray
Write-Host ""

