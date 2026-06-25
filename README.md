Nexus-Flow

Nexus-Flow é uma aplicação projetada para rodar localmente e gerenciar fluxos interativos. O projeto é composto por um backend em Python (Flask) e um frontend simples em HTML/JS, rodando em conjunto com o serviço Foundry Local.

🚀 Como iniciar o projeto

Para rodar a aplicação completa (Backend, Frontend e serviço Foundry), você pode utilizar um dos scripts disponíveis na raiz do projeto:

Usando o arquivo `.bat` (Recomendado no Windows)
Basta dar um duplo clique no arquivo `iniciar.bat` ou rodá-lo pelo terminal:
```cmd
iniciar.bat
```

Usando o PowerShell
Se preferir, você pode rodar o script PowerShell diretamente. Abra o PowerShell na pasta do projeto e execute:
```powershell
.\run.ps1
```

O script cuidará de:
1. Iniciar o serviço local do Foundry.
2. Abrir o servidor do Backend (Flask).
3. Iniciar o servidor web do Frontend (porta 8001).
4. Abrir automaticamente a interface no seu navegador padrão (`http://localhost:8001`).

🛑 Como parar a aplicação

Para encerrar os servidores corretamente e desligar o serviço do Foundry Local, basta fechar a janela do Backend (Flask) que foi aberta ou pressionar `CTRL+C` na janela do terminal onde o script foi executado. O script detectará o encerramento e fechará as demais conexões pendentes de forma segura.

📂 Estrutura do Projeto

- `/backend/`: Contém a API em Flask (`app.py`), gerenciando o serviço principal, e suas dependências (`requirements.txt`).
- `/frontend/`: Contém a interface web (`index.html` e `app.js`).
- **Arquivos `.json` na raiz**: Fluxos exportados/salvos que podem ser carregados e simulados na plataforma (ex: fluxos da *Odete* e *Estella*).
- `run.ps1` e `iniciar.bat`: Scripts de inicialização.

🛠️ Tecnologias Utilizadas
- **Backend:** Python e Flask
- **Frontend:** Vanilla JS e HTML
- **Integração:** Foundry Local Services
