# Быстрые команды для работы с сервером myAssistent
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("status", "logs", "restart", "update", "deploy", "monitor", "backup")]
    [string]$Action
)

$ServerIP = "185.73.215.38"
$Username = "root"
$Password = "GK7gz9yGq15T"

switch ($Action) {
    "status" {
        Write-Host "Проверяю статус сервисов на сервере..." -ForegroundColor Green
        $command = "systemctl status myassistent --no-pager -l"
    }
    "logs" {
        Write-Host "Показываю последние логи..." -ForegroundColor Green
        $command = "journalctl -u myassistent -n 50 --no-pager"
    }
    "restart" {
        Write-Host "Перезапускаю сервис..." -ForegroundColor Green
        $command = "systemctl restart myassistent && systemctl status myassistent --no-pager"
    }
    "update" {
        Write-Host "Обновляю код с GitHub..." -ForegroundColor Green
        $command = "cd ~/myAssistent && git pull origin main && update-myassistent"
    }
    "deploy" {
        Write-Host "Полный деплой..." -ForegroundColor Green
        $command = "cd ~/myAssistent && git pull origin main && update-myassistent && systemctl status myassistent"
    }
    "monitor" {
        Write-Host "Мониторинг в реальном времени..." -ForegroundColor Green
        $command = "journalctl -u myassistent -f"
    }
    "backup" {
        Write-Host "Создаю бэкап..." -ForegroundColor Green
        $command = "cd ~/myAssistent && python -m src.main backup_snapshot"
    }
}

Write-Host "Команда для выполнения:" -ForegroundColor Cyan
Write-Host "ssh $Username@$ServerIP" -ForegroundColor White
Write-Host "cd ~/myAssistent" -ForegroundColor White
Write-Host $command -ForegroundColor White
Write-Host ""
Write-Host "Пароль: $Password" -ForegroundColor Yellow
