# 🌌 Nexus-Flow

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-%23000.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![TailwindCSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![Foundry](https://img.shields.io/badge/Foundry-Local%20Services-orange.svg)](https://github.com/)

> **A plataforma definitiva para diagnóstico, visualização e engenharia reversa de chatbots legados.**

O **Nexus-Flow** é um ecossistema projetado para simplificar a manutenção, documentação e refatoração de fluxos de atendimento automatizados (chatbots). Ele combina a capacidade de processamento de Inteligência Artificial de ponta (através dos modelos Gemini e Groq) com a representação visual padronizada do **BPMN 2.0**, permitindo que equipes técnicas extraiam lógica de sistemas antigos e as tornem legíveis e auditáveis num instante.

---

## 📌 Índice

1. [🚪 Módulos da Aplicação](#-módulos-da-aplicação)
2. [📂 Estrutura do Repositório](#-estrutura-do-repositório)
3. [⚙️ Pré-requisitos](#-pré-requisitos)
4. [🚀 Guia de Início Rápido](#-guia-de-início-rápido)
   - [Execução com `.bat` (Recomendado para Windows)](#execução-com-bat-recomendado-para-windows)
   - [Execução com PowerShell](#execução-com-powershell)
5. [🛑 Como Encerrar a Aplicação](#-como-encerrar-a-aplicação)
6. [🛠️ Arquitetura e Tecnologias](#️-arquitetura-e-tecnologias)
7. [🔒 Variáveis de Ambiente](#-variáveis-de-ambiente)

---

## 🚪 Módulos da Aplicação

O Nexus-Flow está estruturado em três eixos principais de atuação no frontend moderno:

### 1. 🔮 Oráculo de Manutenção (Chat & Analytics)
* **Objetivo:** Responder a dúvidas técnicas, analisar possíveis loops ou inconsistências em regras de negócio e diagnosticar fluxos salvos.
* **Recursos:**
  * Interface conversacional interativa em tempo real (suporte a stream de tokens).
  * Upload e leitura direta de logs de fluxos.
  * Integração com modelos generativos (Gemini e Groq) que recebem o fluxo compactado em um formato super enxuto, reduzindo em até 90% o consumo de tokens.

### 2. 🔀 Conversor Draw.io
* **Objetivo:** Efetuar engenharia reversa de fluxos de atendimento criados de forma gráfica.
* **Recursos:**
  * Importação de diagramas XML/Draw.io exportados diretamente do editor.
  * Parser robusto que mapeia os nós gráficos (`mxGraph`) para a estrutura de dados JSON da Estella.
  * Visualização estruturada da saída em formato de árvore lógica.

### 3. 🎙️ Gerador Inteligente BPMN 2.0
* **Objetivo:** Converter descrições funcionais ou inputs multimodais em diagramas visuais legíveis por humanos e ferramentas de BPMN.
* **Recursos:**
  * **Input Multimodal:** Permite enviar texto detalhado, PDFs de especificação técnica e até gravações de áudio descrevendo o comportamento do bot.
  * **Geração Automática de XML:** Tradução dos requisitos em BPMN 2.0 XML estruturado.
  * **Visualização Integrada:** O frontend utiliza a biblioteca `bpmn-js` para renderizar o diagrama dinamicamente na tela com zoom e pan intuitivos.
  * **Exportação:** Opção de download do XML gerado ou de relatórios em formato PDF.

---

## 📂 Estrutura do Repositório

```bash
Nexus-Flow/
├── backend/                      # API Servidora da Aplicação
│   ├── app.py                    # Servidor Flask principal (Endpoints, Limiter, IA)
│   ├── drawio_parser.py          # Conversor de arquivos .xml/.drawio para JSON
│   ├── translator.py             # Motor de tradução de lógica para BPMN XML
│   ├── requirements.txt          # Dependências Python (Flask, google-genai, etc)
│   ├── Dockerfile                # Configuração para conteinerização do backend
│   └── tests/                    # Testes unitários e de integração
├── frontend/                     # Interface do Usuário (Single Page App)
│   ├── index.html                # Estrutura HTML estilizada via Tailwind e FontAwesome
│   └── app.js                    # Toda a lógica de requisição, áudio e bpmn-js
├── fluxos_demo.json              # Arquivos JSON de exemplo (Ex: Estella Reset, Odete)
├── docker-compose.yml            # Orquestração opcional para serviços isolados
├── iniciar.bat                   # Script de boot simplificado para usuários Windows
└── run.ps1                       # Script completo de automação em PowerShell
```

---

## ⚙️ Pré-requisitos

Para que todos os componentes funcionem localmente, certifique-se de ter instalado:

1. **Python 3.10 ou superior:** Utilizado no backend.
2. **Foundry CLI (Local Services):** A ferramenta utiliza o comando `foundry service` para iniciar dependências no ambiente local.
3. **Navegador Web Moderno:** Google Chrome, Microsoft Edge ou Firefox para carregar a interface interativa.

---

## 🚀 Guia de Início Rápido

A inicialização do Nexus-Flow foi 100% automatizada para que você não precise instalar pacotes ou rodar servidores manualmente. O script cuidará de verificar o ambiente, instalar dependências e iniciar os servidores.

### Execução com `.bat` (Recomendado para Windows)
Dê dois cliques no arquivo `iniciar.bat` localizado na raiz do projeto, ou abra o terminal `cmd` na pasta e execute:
```cmd
iniciar.bat
```

### Execução com PowerShell
Abra um terminal do PowerShell na raiz do projeto e execute:
```powershell
.\run.ps1
```

> [!NOTE]
> **O que o script automatizado faz por baixo dos panos?**
> 1. Restaura o Path do Python caso ele não tenha sido recém-configurado.
> 2. Verifica a existência de uma pasta `venv` no backend. Se ela não existir, cria o ambiente virtual e instala automaticamente todos os pacotes do `requirements.txt`.
> 3. Inicia o serviço Foundry Local (`foundry service start`).
> 4. Dispara o servidor Backend Flask na porta padrão.
> 5. Dispara o servidor web do Frontend (porta `8001`).
> 6. Abre o seu navegador padrão diretamente em `http://localhost:8001`.

---

## 🛑 Como Encerrar a Aplicação

Para encerrar todos os processos em execução de maneira correta e segura:
1. Volte ao console principal do PowerShell onde o script `run.ps1` está rodando e pressione **`CTRL + C`** (ou simplesmente feche a janela do terminal do Backend Flask).
2. O script detectará a parada e executará a rotina de encerramento automático:
   * Desligamento do serviço Foundry Local (`foundry service stop`).
   * Encerramento do processo do servidor web Frontend.
   * Encerramento do processo do backend Flask.

---

## 🛠️ Arquitetura e Tecnologias

* **Frontend:**
  * **TailwindCSS (v3):** Estilização ágil com design moderno (Glassmorphism e paleta de cores elegantes e escuras).
  * **bpmn-js:** Renderização interativa do XML de BPMN gerado no próprio navegador.
  * **marked.js:** Parser Markdown para exibição formatada das respostas do Oráculo de Manutenção.
  * **jsPDF:** Gerador de relatórios executivos em PDF.
* **Backend:**
  * **Flask (Python):** Framework web leve para construir as APIs Rest.
  * **Flask-CORS / Flask-Limiter:** Segurança robusta contra Cross-Origin e controle de concorrência/limitação de requisições.
  * **Google GenAI SDK & Groq SDK:** Integração profunda com modelos avançados para geração de fluxogramas e respostas inteligentes.
  * **Pytest:** Suíte de testes para garantir a corretude do parser e tradutor.

---

## 🔒 Variáveis de Ambiente

As configurações de API estão disponíveis no arquivo [backend/.env](file:///C:/Users/Usu%C3%A1rio/Documents/projetos/Nexus-Flow/backend/.env). Por padrão, chaves de API para desenvolvimento já vêm configuradas para sua conveniência:
* `GEMINI_API_KEY`: Chave para conexão com os modelos Gemini da Google.
* `GROQ_API_KEY`: Chave para conexão com os modelos hospedados na Groq.
* `FOUNDRY_API_BASE`: Endpoint base para integração com o Foundry Local.
* `APP_API_TOKEN`: *(Opcional)* Token do tipo Bearer para segurança adicional de rotas.

---
*Desenvolvido para trazer visibilidade e clareza aos fluxos mais complexos.* 🚀
