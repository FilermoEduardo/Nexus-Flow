Write-Host "=== Iniciando Nexus Flow ===" -ForegroundColor Cyan

# Garante que o Python recém-instalado está no PATH se o console ainda não foi reiniciado
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# 1. Verificar e criar ambiente virtual se necessário
$backendDir = Join-Path $PSScriptRoot "backend"
$venvDir = Join-Path $backendDir "venv"

if (-not (Test-Path $venvDir)) {
    Write-Host "Ambiente virtual (venv) não encontrado no backend. Criando..." -ForegroundColor Yellow
    Push-Location $backendDir
    python -m venv venv
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Ambiente virtual criado. Instalando dependências..." -ForegroundColor Yellow
        & .\venv\Scripts\pip.exe install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Dependências instaladas com sucesso!" -ForegroundColor Green
        }
        else {
            Write-Host "Erro ao instalar dependências. Verifique se o pip está funcionando." -ForegroundColor Red
            Pop-Location
            Exit 1
        }
    }
    else {
        Write-Host "Erro ao criar o ambiente virtual (venv). Verifique se o Python está instalado corretamente." -ForegroundColor Red
        Pop-Location
        Exit 1
    }
    Pop-Location
}

# 2. Iniciar o Backend Flask em uma janela separada
Write-Host "Iniciando o servidor backend (Flask)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\venv\Scripts\activate.ps1; python app.py"

# Aguarda 2 segundos para dar tempo ao Flask subir
Start-Sleep -Seconds 2

# 3. Iniciar o servidor de desenvolvimento para o Frontend na porta 8001 em uma janela separada
Write-Host "Iniciando o servidor do frontend na porta 8001..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; python -m http.server 8001"


# Aguarda 1 segundo
Start-Sleep -Seconds 1

# 4. Abrir o Frontend no navegador
Write-Host "Abrindo a aplicação no navegador..." -ForegroundColor Green
Start-Process "http://localhost:8001"

Write-Host "Tudo pronto! Seus servidores estão rodando em janelas separadas." -ForegroundColor Green

