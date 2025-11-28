# Скрипт для настройки SSH ключей (выполнить один раз)
Write-Host "Настройка SSH ключей для безопасного подключения..." -ForegroundColor Green

# Генерируем SSH ключ (если не существует)
if (-not (Test-Path "$env:USERPROFILE\.ssh\id_rsa")) {
    Write-Host "Генерирую SSH ключ..." -ForegroundColor Yellow
    ssh-keygen -t rsa -b 4096 -f "$env:USERPROFILE\.ssh\id_rsa" -N '""'
}

# Копируем публичный ключ на сервер
Write-Host "Копирую публичный ключ на сервер..." -ForegroundColor Yellow
Write-Host "Выполните эту команду:" -ForegroundColor Cyan
Write-Host "type `$env:USERPROFILE\.ssh\id_rsa.pub | ssh root@185.73.215.38 'cat >> ~/.ssh/authorized_keys'" -ForegroundColor White
Write-Host ""
Write-Host "После этого можно будет подключаться без пароля:" -ForegroundColor Green
Write-Host "ssh root@185.73.215.38" -ForegroundColor White
