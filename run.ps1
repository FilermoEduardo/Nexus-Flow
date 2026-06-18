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

# 2. Iniciar o serviço do Foundry Local
Write-Host "Iniciando o serviço do Foundry Local na porta 8080..." -ForegroundColor Yellow
foundry service start

# 3. Iniciar o Backend Flask em uma janela separada
Write-Host "Iniciando o servidor backend (Flask)..." -ForegroundColor Yellow
$backendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\venv\Scripts\activate.ps1; python app.py" -PassThru

# Aguarda 2 segundos para dar tempo ao Flask subir
Start-Sleep -Seconds 2

# 4. Iniciar o servidor de desenvolvimento para o Frontend na porta 8001 em uma janela separada
Write-Host "Iniciando o servidor do frontend na porta 8001..." -ForegroundColor Yellow
$frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; python -m http.server 8001" -PassThru

# Aguarda 1 segundo
Start-Sleep -Seconds 1

# 5. Abrir o Frontend no navegador
Write-Host "Abrindo a aplicação no navegador..." -ForegroundColor Green
Start-Process "http://localhost:8001"

Write-Host "Tudo pronto! Seus servidores estão rodando em janelas separadas." -ForegroundColor Green
Write-Host "---" -ForegroundColor Cyan
Write-Host "Monitorando os processos..." -ForegroundColor Yellow
Write-Host "Para encerrar o projeto e parar o Foundry Local, feche a janela do Backend (Flask) ou pressione CTRL+C aqui." -ForegroundColor Magenta

try {
    # Aguarda em loop monitorando se o backend foi fechado
    while ($true) {
        if ($backendProcess.HasExited) {
            Write-Host "O servidor Backend (Flask) foi fechado." -ForegroundColor Red
            break
        }
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "Encerrando servidores e desligando o serviço do Foundry Local..." -ForegroundColor Red
    
    # Para o serviço do Foundry Local
    foundry service stop
    
    # Encerra o frontend se ainda estiver ativo
    if ($frontendProcess -and -not $frontendProcess.HasExited) {
        Stop-Process -Id $frontendProcess.Id -Force
    }
    
    # Encerra o backend se ainda estiver ativo
    if ($backendProcess -and -not $backendProcess.HasExited) {
        Stop-Process -Id $backendProcess.Id -Force
    }
}

