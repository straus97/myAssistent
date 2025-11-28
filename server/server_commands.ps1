# Скрипт для выполнения команд на сервере
param(
    [Parameter(Mandatory=$true)]
    [string]$Command,
    [string]$ServerIP = "185.73.215.38",
    [string]$Username = "root"
)

$Password = "GK7gz9yGq15T"

Write-Host "Выполняю команду на сервере: $Command" -ForegroundColor Green

# Создаем временный файл с командой
$tempScript = "temp_server_command.sh"
$Command | Out-File -FilePath $tempScript -Encoding UTF8

try {
    # Выполняем команду через SSH
    $sshCommand = "ssh -o StrictHostKeyChecking=no $Username@$ServerIP 'cd ~/myAssistent && bash -s' < $tempScript"
    
    # Используем expect для автоматического ввода пароля (если доступен)
    if (Get-Command plink -ErrorAction SilentlyContinue) {
        plink -ssh -pw $Password $Username@$ServerIP "cd ~/myAssistent && $Command"
    } else {
        Write-Host "Для автоматического ввода пароля установите PuTTY (plink.exe)" -ForegroundColor Yellow
        Write-Host "Или выполните команду вручную:" -ForegroundColor Yellow
        Write-Host "ssh $Username@$ServerIP" -ForegroundColor Cyan
        Write-Host "cd ~/myAssistent" -ForegroundColor Cyan
        Write-Host $Command -ForegroundColor Cyan
    }
} finally {
    # Удаляем временный файл
    if (Test-Path $tempScript) {
        Remove-Item $tempScript
    }
}
