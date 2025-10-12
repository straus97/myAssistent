@echo off
chcp 65001 >NUL
setlocal EnableDelayedExpansion

REM Получаем API_KEY из .env
for /f "usebackq tokens=1,* delims==" %%a in (.env) do (
    if "%%a"=="API_KEY" set "API_KEY=%%b"
)

if not defined API_KEY (
    echo [ERROR] API_KEY не найден в .env
    pause
    exit /b 1
)

echo ========================================
echo   Paper Trading Status Check
echo ========================================
echo.

REM 1. Paper Monitor Status
echo [1/4] Paper Monitor Status...
curl -s -X GET "http://localhost:8000/paper-monitor/status" -H "X-API-Key: %API_KEY%" > temp_status.json
powershell -Command "$json = Get-Content temp_status.json | ConvertFrom-Json; Write-Host '  Enabled:' $json.enabled; Write-Host '  Equity: $'([math]::Round($json.equity.equity, 2)); Write-Host '  Positions:' $json.positions_count; Write-Host '  Updates:' $json.stats.total_updates; Write-Host '  Signals:' $json.stats.total_signals; Write-Host '  Errors:' $json.stats.errors"
del temp_status.json

echo.
echo [2/4] Risk Management...
curl -s -X GET "http://localhost:8000/risk-management/exposure" -H "X-API-Key: %API_KEY%" > temp_risk.json
powershell -Command "$json = Get-Content temp_risk.json | ConvertFrom-Json; Write-Host '  Exposure:' ([math]::Round($json.exposure_pct, 1))'%%'; Write-Host '  Status:' $json.status; if ($json.message) { Write-Host '  Warning:' $json.message }"
del temp_risk.json

echo.
echo [3/4] Health Check...
curl -s -X GET "http://localhost:8000/health" > temp_health.json
powershell -Command "$json = Get-Content temp_health.json | ConvertFrom-Json; Write-Host '  System Status:' $json.status; Write-Host '  Database:' $json.services.database; Write-Host '  Scheduler:' $json.services.scheduler; Write-Host '  Model:' $json.services.model"
del temp_health.json

echo.
echo [4/4] Recent Signals...
curl -s -X GET "http://localhost:8000/signals/recent?limit=5" > temp_signals.json
powershell -Command "$json = Get-Content temp_signals.json | ConvertFrom-Json; if ($json.data.Count -gt 0) { Write-Host '  Found' $json.data.Count 'signals'; foreach ($sig in $json.data | Select-Object -First 3) { Write-Host '   ' $sig.symbol '-' $sig.signal } } else { Write-Host '  No recent signals' }"
del temp_signals.json

echo.
echo ========================================
echo   Check complete!
echo ========================================
echo.
echo Quick links:
echo   Swagger UI:  http://localhost:8000/docs
echo   Dashboard:   http://localhost:3000
echo   MLflow:      http://localhost:5000
echo   Grafana:     http://localhost:3001
echo.
pause

