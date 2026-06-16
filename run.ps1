Write-Host "=== Iniciando Nexus Flow ===" -ForegroundColor Cyan

# Garante que o Python recém-instalado está no PATH se o console ainda não foi reiniciado
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# 1. Iniciar o Backend Flask em uma janela separada
Write-Host "Iniciando o servidor backend (Flask)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\venv\Scripts\activate.ps1; python app.py"

# Aguarda 2 segundos para dar tempo ao Flask subir
Start-Sleep -Seconds 2

# 2. Iniciar o servidor de desenvolvimento para o Frontend na porta 8001 em uma janela separada
Write-Host "Iniciando o servidor do frontend na porta 8001..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; python -m http.server 8001"


# Aguarda 1 segundo
Start-Sleep -Seconds 1

# 3. Abrir o Frontend no navegador
Write-Host "Abrindo a aplicação no navegador..." -ForegroundColor Green
Start-Process "http://localhost:8001"

Write-Host "Tudo pronto! Seus servidores estão rodando em janelas separadas." -ForegroundColor Green

