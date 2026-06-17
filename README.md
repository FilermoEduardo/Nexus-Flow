# Nexus-Flow 🚀

O **Nexus-Flow** é uma plataforma inteligente e moderna para **diagnóstico, visualização e engenharia reversa de fluxos de chatbots legados**. Com o auxílio de Inteligência Artificial generativa (Google Gemini ou modelos locais com Ollama), a ferramenta converte descrições textuais, regras de negócio em PDFs, imagens de diagramas e narrações em áudio diretamente em diagramas formais de processo padrão **BPMN 2.0 XML** e fluxos JSON estruturados.

---

## 🌟 Principais Recursos

1. **Gerador Inteligente BPMN 2.0**:
   * Interpretação multimodal de entradas (Áudio, Imagem, PDF ou Texto).
   * Geração automatizada de diagramas BPMN ricos com suporte a raias de responsabilidade (Swimlanes/Pools).
   * Algoritmo de **Auto-Layout Dinâmico** que organiza elementos em colunas e ajusta a altura das raias de forma inteligente, evitando sobreposições.
   * Classificação técnica automática de elementos (ex: `userTask`, `serviceTask`, `sendTask`, `timerEventDefinition`, `terminateEventDefinition`).
   * Padronização gramatical semântica: nomes de tarefas iniciados com verbo no infinitivo e eventos no particípio.

2. **Oráculo de Manutenção**:
   * Chat interativo com a IA com respostas em **Streaming em tempo real** (via Server-Sent Events - SSE).
   * Upload de arquivos JSON de fluxogramas legados para diagnóstico e análise rápida.
   * Extração de métricas de engenharia (quantidade de nós, gateways, scripts e integrações).
   * Exportação do histórico da conversa de análise estruturada diretamente para **PDF**.

3. **Visualizador Interativo Integrado**:
   * Renderização gráfica na tela em tempo real utilizando a biblioteca `bpmn-js`.
   * Tela de visualização com alto contraste e nitidez.
   * Recurso de **Exportação de SVG** baseado em Promises para baixar a imagem do diagrama com um clique.

4. **Refinamento Iterativo via Prompts**:
   * Permite conversar com a IA para ajustar trechos específicos do diagrama gerado em tempo real sem precisar reiniciar o processo.

---

## 🛠️ Tecnologias Utilizadas

### Backend
* **Python 3.10+**
* **Flask** (com Flask-CORS e Flask-Limiter para Rate Limiting)
* **Google Generative AI SDK** (Modelos Gemini)
* **jsonschema** (Validação robusta de esquemas JSON)
* **pytest** (Suíte de testes automatizados e unitários)

### Frontend
* **HTML5** & **Tailwind CSS** (Interface premium com efeitos de Glassmorphism e Dark Mode)
* **Vanilla JavaScript** (Lógica reativa e tratamento de streams)
* **bpmn-js** (Visualização e manipulação do diagrama)
* **jsPDF** (Geração de relatórios PDF)
* **marked.js** (Parser progressivo de Markdown no chat)

---

## 📁 Estrutura do Projeto

```text
Nexus-Flow/
├── backend/
│   ├── app.py                  # Servidor Flask, rotas de API, validações e prompts
│   ├── translator.py           # Algoritmo de auto-layout e tradução JSON para XML BPMN
│   ├── drawio_parser.py        # Parser de diagramas importados do Draw.io
│   ├── requirements.txt        # Dependências Python do backend
│   └── tests/                  # Suíte de testes automatizados (pytest)
├── frontend/
│   ├── index.html              # Relação estrutural da interface do usuário
│   └── app.js                  # Lógica do cliente, conexão SSE e manipulação do BPMN
├── BACKLOG_XML_EVOLUTION.md    # Plano de evolução da arquitetura de esquemas
├── run.ps1                     # Script Powershell para inicialização automatizada
└── README.md                   # Documentação principal do projeto
```

---

## 🚀 Como Executar o Projeto

### Pré-requisitos
* **Python 3.10** ou superior instalado e configurado no PATH.
* Chave de API do Gemini para as funcionalidades inteligentes na nuvem.

### Passo 1: Configuração das Variáveis de Ambiente
Na pasta `/backend`, crie um arquivo chamado `.env` e configure sua chave da API do Gemini e o token de autenticação:

```env
GEMINI_API_KEY=sua_chave_aqui
APP_API_TOKEN=seu_token_de_seguranca_opcional
```

### Passo 2: Execução Rápida (PowerShell)
O projeto conta com um script de inicialização automática em PowerShell (`run.ps1`). Ele cria o ambiente virtual do Python (`venv`), instala as dependências, inicia o servidor do backend e do frontend e abre a aplicação no seu navegador padrão.

Abra o terminal do PowerShell na raiz do projeto e execute:
```powershell
.\run.ps1
```

A aplicação estará disponível em:
* **Frontend**: `http://localhost:8001`
* **Backend API**: `http://localhost:5000`

---

## 🧪 Rodando os Testes Automatizados

Para validar se todas as rotas e o tradutor BPMN estão em perfeito funcionamento e sem regressões, execute os testes com o pytest dentro da pasta `backend`:

```bash
cd backend
.\venv\Scripts\python -m pytest
```
