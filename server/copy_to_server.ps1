# Скрипт для копирования файлов на Ubuntu сервер

$serverIP = "185.73.215.38"
$serverUser = "root"
$serverPath = "/root/myAssistent"

Write-Host "Копирование файлов на сервер $serverIP..." -ForegroundColor Cyan

# Используем scp для копирования
scp -o StrictHostKeyChecking=no `
    ЗАПУСК_PAPER_TRADING_СЕРВЕР.md `
    server_diagnostics.sh `
    ${serverUser}@${serverIP}:${serverPath}/

Write-Host "Файлы скопированы! Теперь подключитесь к серверу:" -ForegroundColor Green
Write-Host "ssh root@185.73.215.38" -ForegroundColor Yellow
Write-Host "Пароль: GK7gz9yGq15T" -ForegroundColor Yellow



