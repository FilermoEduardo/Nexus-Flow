# Backlog de Melhorias - Nexus-Flow

Este documento contém o plano de ação com as melhorias propostas para o projeto **Nexus-Flow**. Ele está estruturado para orientar um agente de inteligência artificial ou desenvolvedor na implementação passo a passo de cada nova funcionalidade, divididas em duas fases: aprimoramento de experiência (Fase 1) e prontidão para produção/segurança (Fase 2).

---

## 📌 Sumário de Melhorias

### Fase 1: Core UX e Estabilidade Técnica (Interface e Interações)
1. **[Melhoria 1: Visualizador Interativo de BPMN 2.0 integrado](#melhoria-1-visualizador-interativo-de-bpmn-20-integrado)** (Prioridade: Alta)
2. **[Melhoria 2: Streaming de Respostas da IA no Oráculo de Manutenção](#melhoria-2-streaming-de-respostas-da-ia-no-oraculo-de-manutencao)** (Prioridade: Alta)
3. **[Melhoria 3: Persistência de Conversas e Configurações (LocalStorage)](#melhoria-3-persistencia-de-conversas-e-configuracoes-localstorage)** (Prioridade: Média)
4. **[Melhoria 4: Refinamento Iterativo de Fluxo BPMN via Prompts](#melhoria-4-refinamento-iterativo-de-fluxo-bpmn-via-prompts)** (Prioridade: Média)
5. **[Melhoria 5: Validação Robusta de Schemas de Fluxo no Backend](#melhoria-5-validacao-robusta-de-schemas-de-fluxo-no-backend)** (Prioridade: Baixa)

### Fase 2: Segurança, Qualidade e Infraestrutura (Escalabilidade e Produção)
6. **[Melhoria 6: Segurança e Controle de Acesso (Rate Limiting & Autenticação)](#melhoria-6-seguranca-e-controle-de-acesso-rate-limiting--autenticacao)** (Prioridade: Alta)
7. **[Melhoria 7: Suíte de Testes Automatizados no Backend](#melhoria-7-suite-de-testes-automatizados-no-backend)** (Prioridade: Média)
8. **[Melhoria 8: Containerização com Docker e Docker Compose](#melhoria-8-containerizacao-com-docker-e-docker-compose)** (Prioridade: Média)
9. **[Melhoria 9: Exportação de Relatórios e Imagens do Fluxo](#melhoria-9-exportacao-de-relatorios-e-imagens-do-fluxo)** (Prioridade: Baixa)

---

## 🛠️ Detalhamento Técnico e Plano de Ação

### Melhoria 1: Visualizador Interativo de BPMN 2.0 integrado

* **Objetivo:** Renderizar o diagrama BPMN gerado no módulo **Gerador Inteligente** em tempo real na tela, permitindo ao usuário conferir visualmente o fluxo criado pela IA antes de realizar o download.
* **Ferramentas sugeridas:** Biblioteca [bpmn-js](https://bpmn.io/toolkit/bpmn-js/) (distribuição via CDN).
* **Arquivos envolvidos:**
  * [frontend/index.html](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/index.html)
  * [frontend/app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js)

#### 📝 Plano de Ação para a IA:
1. **Atualizar o HTML:**
   * No arquivo [index.html](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/index.html), insira o link da CDN do `bpmn-viewer` na tag `<head>`:
     ```html
     <script src="https://unpkg.com/bpmn-js@17.0.2/dist/bpmn-viewer.production.min.js"></script>
     ```
   * Dentro do container de download do gerador inteligente (`id="generator-download-box"`), adicione uma área destinada para a renderização do diagrama:
     ```html
     <div id="bpmn-canvas" class="w-full h-[450px] bg-slate-900/60 border border-slate-800 rounded-xl my-4 overflow-hidden relative"></div>
     ```
2. **Atualizar a Lógica JavaScript:**
   * No arquivo [app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js), declare uma instância global do visualizador BPMN:
     ```javascript
     let bpmnViewer = null;
     ```
   * Crie uma função dedicada para inicializar e renderizar o XML do BPMN:
     ```javascript
     function renderBPMNDiagram(xmlString) {
         const container = document.getElementById('bpmn-canvas');
         if (!bpmnViewer) {
             bpmnViewer = new BpmnJS({ container: container });
         }
         bpmnViewer.importXML(xmlString).then(() => {
             const canvas = bpmnViewer.get('canvas');
             canvas.zoom('fit-viewport');
         }).catch(err => {
             console.error('Erro ao renderizar diagrama BPMN:', err);
         });
     }
     ```
   * Na rota de geração de fluxo (evento do botão `btn-generate-flow`), capture a resposta em formato XML (texto bruto) e, em caso de sucesso, chame `renderBPMNDiagram(xmlString)` antes de exibir o `generator-download-box`.

---

### Melhoria 2: Streaming de Respostas da IA no Oráculo de Manutenção

* **Objetivo:** Otimizar o tempo de resposta percebido pelo usuário ao mostrar os tokens da IA sendo gerados progressivamente (streaming), ao invés de aguardar a resposta inteira em lote.
* **Ferramentas sugeridas:** Server-Sent Events (SSE) ou chamadas de stream no Flask, ReadableStream no JavaScript.
* **Arquivos envolvidos:**
  * [backend/app.py](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/app.py)
  * [frontend/app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js)

#### 📝 Plano de Ação para a IA:
1. **Refatorar o Backend:**
   * No [app.py](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/app.py), ajuste a função `generate_llm_response` para suportar um modo gerador (yield) ao utilizar a API do Gemini:
     ```python
     # Quando stream=True:
     response = model.generate_content(contents, generation_config=generation_config, stream=True)
     for chunk in response:
         yield chunk.text
     ```
   * Crie uma nova rota no Flask `/chat-stream` (ou altere `/chat`) que utilize a classe `Response` do Flask para retornar o stream com mimetype `text/event-stream`:
     ```python
     from flask import Response
     
     @app.route('/chat-stream', methods=['POST'])
     def chat_stream():
         # Lógica de obtenção de parâmetros (question, flow_data, etc.)
         def generate():
             for token in generate_llm_response(prompt, provider, model_name, attached_file, stream=True):
                 yield f"data: {json.dumps({'token': token})}\n\n"
         return Response(generate(), mimetype='text/event-stream')
     ```
2. **Refatorar o Frontend:**
   * No [app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js), substitua a requisição fetch comum por um leitor de streams na função `sendChatMessage()`:
     ```javascript
     const response = await fetch(`${API_BASE_URL}/chat-stream`, {
         method: 'POST',
         body: formData,
         headers: { 'X-Provider-Model': selectedModel }
     });
     
     const reader = response.body.getReader();
     const decoder = new TextDecoder();
     let partialText = '';
     
     // Criar o container da mensagem da IA vazio primeiro
     let aiMessageDiv = addMessage('ai', '');
     
     while (true) {
         const { value, done } = await reader.read();
         if (done) break;
         
         const chunk = decoder.decode(value, { stream: true });
         // Fazer parse das linhas de evento 'data: ...'
         const lines = chunk.split('\n');
         for (const line of lines) {
             if (line.startsWith('data: ')) {
                 try {
                     const json = JSON.parse(line.substring(6));
                     partialText += json.token;
                     
                     // Atualizar o HTML da mensagem renderizando o Markdown progressivo
                     aiMessageDiv.innerHTML = marked.parse(partialText);
                     // Reaplicar estilizações e scroll vertical
                     chatMessages.scrollTop = chatMessages.scrollHeight;
                 } catch (e) {}
             }
         }
     }
     ```

---

### Melhoria 3: Persistência de Conversas e Configurações (LocalStorage)

* **Objetivo:** Armazenar o histórico de mensagens trocadas com o Oráculo de forma local para evitar que o usuário perca suas análises e logs ao recarregar o navegador.
* **Ferramentas sugeridas:** `localStorage` do navegador.
* **Arquivos envolvidos:**
  * [frontend/app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js)

#### 📝 Plano de Ação para a IA:
1. **Estruturar Armazenamento do Chat:**
   * Implemente uma chave única de indexação baseada no nome do arquivo carregado ou hash do JSON (ex: `chat_history_${fileName}`).
2. **Função de Salvamento:**
   * Crie uma função `saveChatHistory()` em [app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js) que capture o array de mensagens e o salve serializado como JSON no `localStorage`:
     ```javascript
     function saveChatHistory(fileName, messages) {
         localStorage.setItem(`chat_history_${fileName}`, JSON.stringify(messages));
     }
     ```
3. **Função de Carregamento:**
   * Ao detectar o upload bem-sucedido de um fluxo JSON no `jsonUpload.addEventListener`, chame a função `loadChatHistory(file.name)`:
     ```javascript
     function loadChatHistory(fileName) {
         const historyRaw = localStorage.getItem(`chat_history_${fileName}`);
         if (historyRaw) {
             const messages = JSON.parse(historyRaw);
             chatMessages.innerHTML = ''; // Limpar aviso padrão
             messages.forEach(msg => {
                 addMessage(msg.sender, msg.text);
             });
         }
     }
     ```
   * Modifique a função `addMessage()` para acumular a mensagem em uma pilha de estado local antes de salvar.

---

### Melhoria 4: Refinamento Iterativo de Fluxo BPMN via Prompts

* **Objetivo:** Permitir que o usuário ajuste e refine um fluxo gerado dinamicamente enviando comandos adicionais por chat (ex: *"Adicionar uma validação de CPF depois do nó de identificação"*), em vez de recomeçar todo o fluxo do zero.
* **Arquivos envolvidos:**
  * [backend/app.py](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/app.py)
  * [frontend/index.html](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/index.html)
  * [frontend/app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js)

#### 📝 Plano de Ação para a IA:
1. **Adaptar o Backend para Refinamentos:**
   * Crie uma nova rota `/refine-flow` no [app.py](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/app.py) que receba o JSON do fluxo existente (`current_flow`) e a instrução de mudança (`refinement_instruction`).
   * No prompt enviado à IA, inclua o JSON anterior e detalhe que apenas as alterações solicitadas devem ser implementadas, preservando o máximo possível a estrutura original dos IDs de nós e conexões existentes.
2. **Atualizar a Interface do Gerador:**
   * Adicione uma barra de digitação de chat de refinamento no módulo Gerador Inteligente abaixo da caixa de download.
   * Ao submeter o comando, envie o JSON atual armazenado na memória da página com a nova instrução para `/refine-flow`.
   * Substitua o XML antigo pelo novo no visualizador e no link de download do BPMN.

---

### Melhoria 5: Validação Robusta de Schemas de Fluxo no Backend

* **Objetivo:** Garantir a integridade do JSON de chatbot da Estella recebido pelo backend nas rotas de processamento, evitando que erros silenciosos de sintaxe ou propriedades corrompidas quebrem os tradutores de BPMN ou os LLMs.
* **Ferramentas sugeridas:** Biblioteca `jsonschema` ou `pydantic` em Python.
* **Arquivos envolvidos:**
  * [backend/app.py](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/app.py)
  * [backend/requirements.txt](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/requirements.txt)

#### 📝 Plano de Ação para a IA:
1. **Adicionar Dependência:**
   * Inclua `jsonschema` no arquivo [requirements.txt](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/requirements.txt).
2. **Criar Estrutura de Validação:**
   * No [app.py](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/app.py), defina o schema esperado para o nó e para a conexão:
     ```python
     FLOW_SCHEMA = {
         "type": "array",
         "items": {
             "type": "object",
             "properties": {
                 "id": {"type": ["integer", "string"]},
                 "parent": {"type": ["integer", "string", "null"]},
                 "edge": {"type": "integer"},
                 "cod_componente": {"type": "integer"},
                 "name": {"type": "string"}
             },
             "required": ["id"]
         }
     }
     ```
3. **Validar Requisições:**
   * Na rota `/upload` e `/chat`, antes de iniciar a extração ou análise lógica, execute a validação:
     ```python
     from jsonschema import validate, ValidationError
     
     try:
         validate(instance=flow_data, schema=FLOW_SCHEMA)
     except ValidationError as ve:
         return jsonify({"error": f"Schema do fluxo inválido: {ve.message}"}), 400
     ```

---

### Melhoria 6: Segurança e Controle de Acesso (Rate Limiting & Autenticação)

* **Objetivo:** Proteger as rotas de API do backend contra uso malicioso, ataques de negação de serviço (DDoS) ou consumo excessivo e descontrolado das cotas das chaves de API da IA.
* **Ferramentas sugeridas:** `Flask-Limiter` para rate limiting, autenticação básica via Token ou JWT (JSON Web Tokens).
* **Arquivos envolvidos:**
  * [backend/app.py](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/app.py)
  * [backend/requirements.txt](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/requirements.txt)

#### 📝 Plano de Ação para a IA:
1. **Configurar o Rate Limiter:**
   * Instale o `Flask-Limiter` adicionando-o ao [requirements.txt](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/requirements.txt).
   * Inicialize a extensão no [app.py](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/app.py):
     ```python
     from flask_limiter import Limiter
     from flask_limiter.util import get_remote_address
     
     limiter = Limiter(
         key_func=get_remote_address,
         app=app,
         default_limits=["200 per day", "50 per hour"]
     )
     ```
   * Proteja endpoints custosos como `/chat` e `/generate-multimodal` com limites específicos (ex: `@limiter.limit("5 per minute")`).
2. **Implementar Autenticação:**
   * Crie uma chave secreta no `.env` (ex: `APP_API_TOKEN`).
   * Adicione um decorador ou checagem `before_request` no Flask para validar a presença e o valor de um header de autorização (ex: `Authorization: Bearer <token>`) em todas as rotas críticas.

---

### Melhoria 7: Suíte de Testes Automatizados no Backend

* **Objetivo:** Assegurar a integridade do código do tradutor BPMN e dos endpoints, facilitando futuras refatorações sem risco de quebras silenciosas.
* **Ferramentas sugeridas:** `pytest` para testes unitários e de integração.
* **Arquivos envolvidos:**
  * Criação de `backend/tests/test_translator.py`
  * Criação de `backend/tests/test_api.py`
  * [backend/requirements.txt](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/requirements.txt)

#### 📝 Plano de Ação para a IA:
1. **Instalar pytest:**
   * Adicione `pytest` no [requirements.txt](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/backend/requirements.txt).
2. **Escrever testes para o Tradutor:**
   * Crie o arquivo `backend/tests/test_translator.py` e teste a lógica da função `generate_bpmn_xml` com diferentes configurações de nós (início, fim, gateways, tarefas comuns). Garanta que a estrutura XML gerada contém as tags `<bpmn:startEvent>`, `<bpmn:task>`, etc.
3. **Escrever testes de Integração para a API:**
   * Crie o arquivo `backend/tests/test_api.py` utilizando o cliente de testes integrado do Flask (`app.test_client()`) para disparar requisições simuladas para `/upload`, `/chat` e `/convert-drawio`, validando os códigos de status HTTP (200, 400, etc.).

---

### Melhoria 8: Containerização com Docker e Docker Compose

* **Objetivo:** Uniformizar o ambiente de execução entre desenvolvimento e produção, permitindo rodar tanto o backend em Flask quanto o servidor frontend de forma isolada, rápida e consistente.
* **Ferramentas sugeridas:** Docker, Docker Compose.
* **Arquivos envolvidos:**
  * Criação de `Dockerfile` (na pasta raiz ou dentro de `backend/`)
  * Criação de `docker-compose.yml` (na pasta raiz)

#### 📝 Plano de Ação para a IA:
1. **Criar Dockerfile para o Backend:**
   * Monte uma imagem base em Python 3.10-slim.
   * Copie o diretório `backend`, instale as dependências de `requirements.txt` e exponha a porta `5000`.
2. **Criar Dockerfile para o Frontend (Opcional ou Servidor Estático):**
   * Monte uma imagem base com `nginx:alpine`.
   * Copie os arquivos da pasta `frontend` para o diretório `/usr/share/nginx/html` e exponha a porta `80`.
3. **Criar o docker-compose.yml:**
   * Configure dois serviços: `backend` e `frontend`.
   * Mapeie os volumes locais para desenvolvimento ágil e defina o repasse de portas de rede. Adicione as variáveis de ambiente necessárias (como a `GEMINI_API_KEY`) ligando-as às variáveis da máquina host.

---

### Melhoria 9: Exportação de Relatórios e Imagens do Fluxo

* **Objetivo:** Aumentar o valor das entregas do sistema permitindo que os desenvolvedores exportem a documentação gerada pelo Oráculo ou os diagramas do gerador em formatos legíveis para relatórios executivos.
* **Ferramentas sugeridas:** `bpmn-to-image` (utilidade CLI ou integrada no bpmn-js), jsPDF ou geração de relatórios Markdown convertidos para PDF no backend.
* **Arquivos envolvidos:**
  * [frontend/index.html](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/index.html)
  * [frontend/app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js)

#### 📝 Plano de Ação para a IA:
1. **Exportar Diagrama BPMN como Imagem:**
   * No [app.js](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/app.js), utilize a API nativa do `bpmn-js` para salvar o canvas SVG/PNG:
     ```javascript
     bpmnViewer.saveSVG((err, svg) => {
         // Lógica para transformar o SVG em blob e disparar download do arquivo .svg
     });
     ```
   * Crie um botão *"Exportar como SVG"* na tela do gerador.
2. **Geração de PDF do Histórico do Oráculo:**
   * Adicione uma biblioteca como `jspdf` ou `html2pdf.js` via CDN no [index.html](file:///C:/Users/FilermoEduardo/Documents/Projetos/Nexus-Flow/frontend/index.html).
   * Implemente um botão no cabeçalho do Oráculo para gerar um relatório estruturado em PDF contendo o histórico completo da conversa, o sumário e as métricas do chatbot analisado.
