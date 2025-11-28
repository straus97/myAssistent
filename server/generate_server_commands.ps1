# Генератор команд для сервера myAssistent
# Этот скрипт создает готовые команды для копирования

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("check_status", "view_logs", "restart_service", "update_code", "check_trading", "backup_data", "monitor_realtime")]
    [string]$Action
)

$ServerIP = "185.73.215.38"
$Username = "root"

Write-Host "=== КОМАНДЫ ДЛЯ СЕРВЕРА ===" -ForegroundColor Green
Write-Host "Подключение: ssh $Username@$ServerIP" -ForegroundColor Cyan
Write-Host "Пароль: GK7gz9yGq15T" -ForegroundColor Yellow
Write-Host ""

switch ($Action) {
    "check_status" {
        Write-Host "=== ПРОВЕРКА СТАТУСА СЕРВИСА ===" -ForegroundColor Green
        Write-Host "cd ~/myAssistent" -ForegroundColor White
        Write-Host "systemctl status myassistent --no-pager -l" -ForegroundColor White
        Write-Host "ps aux | grep python" -ForegroundColor White
    }
    "view_logs" {
        Write-Host "=== ПРОСМОТР ЛОГОВ ===" -ForegroundColor Green
        Write-Host "cd ~/myAssistent" -ForegroundColor White
        Write-Host "journalctl -u myassistent -n 100 --no-pager" -ForegroundColor White
        Write-Host "tail -f logs/app.log" -ForegroundColor White
    }
    "restart_service" {
        Write-Host "=== ПЕРЕЗАПУСК СЕРВИСА ===" -ForegroundColor Green
        Write-Host "cd ~/myAssistent" -ForegroundColor White
        Write-Host "systemctl restart myassistent" -ForegroundColor White
        Write-Host "systemctl status myassistent --no-pager" -ForegroundColor White
    }
    "update_code" {
        Write-Host "=== ОБНОВЛЕНИЕ КОДА ===" -ForegroundColor Green
        Write-Host "cd ~/myAssistent" -ForegroundColor White
        Write-Host "git pull origin main" -ForegroundColor White
        Write-Host "update-myassistent" -ForegroundColor White
    }
    "check_trading" {
        Write-Host "=== ПРОВЕРКА ТОРГОВЛИ ===" -ForegroundColor Green
        Write-Host "cd ~/myAssistent" -ForegroundColor White
        Write-Host "python -m src.main trade_positions" -ForegroundColor White
        Write-Host "python -m src.main trade_equity" -ForegroundColor White
        Write-Host "cat artifacts/paper_state.json | jq ." -ForegroundColor White
    }
    "backup_data" {
        Write-Host "=== СОЗДАНИЕ БЭКАПА ===" -ForegroundColor Green
        Write-Host "cd ~/myAssistent" -ForegroundColor White
        Write-Host "python -m src.main backup_snapshot" -ForegroundColor White
        Write-Host "ls -la artifacts/backups/" -ForegroundColor White
    }
    "monitor_realtime" {
        Write-Host "=== МОНИТОРИНГ В РЕАЛЬНОМ ВРЕМЕНИ ===" -ForegroundColor Green
        Write-Host "cd ~/myAssistent" -ForegroundColor White
        Write-Host "journalctl -u myassistent -f" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "=== ИНСТРУКЦИЯ ===" -ForegroundColor Yellow
Write-Host "1. Скопируйте команды выше" -ForegroundColor White
Write-Host "2. Подключитесь к серверу: ssh $Username@$ServerIP" -ForegroundColor White
Write-Host "3. Введите пароль: GK7gz9yGq15T" -ForegroundColor White
Write-Host "4. Выполните команды по порядку" -ForegroundColor White
Write-Host "5. Результат покажите мне" -ForegroundColor White
