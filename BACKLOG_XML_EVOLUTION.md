# Backlog de Evolução - Esquema JSON e Tradução BPMN 2.0

Este documento detalha o plano de ação técnico para implementar a evolução na geração e tradução dos fluxos de chatbot do **Nexus-Flow** para o padrão BPMN 2.0 XML. O objetivo é enriquecer o esquema de dados trafegado entre a IA e o backend, estruturar raias (Swimlanes/Pools) de responsabilidade, tipificar tarefas/eventos e padronizar a semântica textual dos nomes dos nós.

---

## 📌 Sumário de Tarefas

1. **[Evolução do Esquema JSON (Saída da IA)](#1-evolução-do-esquema-json-saída-da-ia)**
2. **[Adaptação do translator.py (Tradução para XML)](#2-adaptação-do-translatorpy-tradução-para-xml)**
3. **[Ajuste de Engenharia de Prompt (Gramática e Semântica)](#3-ajuste-de-engenharia-de-prompt-gramática-e-semântica)**
4. **[Atualização dos Testes Automatizados](#4-atualização-dos-testes-automatizados)**

---

## 🛠️ Detalhamento Técnico e Plano de Ação

### 1. Evolução do Esquema JSON (Saída da IA)

* **Objetivo:** Adicionar propriedades semânticas adicionais ao JSON do fluxo gerado e refinado pela IA para suportar papéis (lanes), tipos específicos de tarefas (task_type) e tipos específicos de eventos (event_type).
* **Arquivos envolvidos:**
  * [backend/app.py](file:///c:/Users/Usuário/Documents/projetos/Nexus-Flow/backend/app.py)

#### 📝 Plano de Ação:
1. **Atualizar `FLOW_SCHEMA` em `app.py`**:
   * Adicione as novas chaves ao dicionário de validação JSON:
     * `"lane"`: tipo `string` (opcional, indica o papel/setor responsável).
     * `"task_type"`: tipo `string` com restrição de enum: `["user", "service", "manual", "script", "send", "receive"]`.
     * `"event_type"`: tipo `string` com restrição de enum: `["timer", "error", "terminate", "message"]`.
2. **Modificar a filtragem de chaves em `app.py`**:
   * Certifique-se de que a filtragem de chaves para economizar tokens (`logical_keys` nas rotas `/chat` e `/chat-stream`) inclua as novas chaves: `"lane"`, `"task_type"`, `"event_type"`.
3. **Exemplo do esquema esperado da IA**:
   ```json
   {
     "flow": [
       {
         "id": 1,
         "parent": null,
         "edge": 0,
         "cod_componente": 17,
         "task_type": "user",
         "lane": "Suporte Técnico",
         "name": "Verificar histórico do cliente"
       },
       {
         "id": 2,
         "parent": 1,
         "edge": 0,
         "cod_componente": 11,
         "event_type": "timer",
         "lane": "Suporte Técnico",
         "name": "Aguardar 5 minutos"
       }
     ]
   }
   ```

---

### 2. Adaptação do translator.py (Tradução para XML)

* **Objetivo:** Adaptar o tradutor para ler o JSON enriquecido e mapear as tags corretas de atividades, eventos e organizar os elementos em raias (Swimlanes) e piscinas (Pools) de colaboração.
* **Arquivos envolvidos:**
  * [backend/translator.py](file:///c:/Users/Usuário/Documents/projetos/Nexus-Flow/backend/translator.py)

#### 📝 Plano de Ação:
1. **Mapeamento de Tags e Definições de Execução**:
   * Ao processar nós de tarefa (`cod_componente: 17`):
     * Se `"task_type": "user"`, gere a tag `<bpmn:userTask id="..." name="...">` (em vez de `<bpmn:task>`).
     * Se `"task_type": "service"`, gere a tag `<bpmn:serviceTask id="..." name="...">`.
     * Para outros tipos (`manual`, `script`, etc.), mapeie para suas respectivas tags BPMN equivalentes ou use `<bpmn:task>` caso não aplicável.
   * Ao processar eventos de início/fim/intermediários contendo `"event_type"`:
     * Se `"event_type": "timer"`, inclua a tag filha `<bpmn:timerEventDefinition />` dentro do evento correspondente no XML.
     * Se `"event_type": "terminate"`, inclua a tag filha `<bpmn:terminateEventDefinition />` dentro do evento correspondente no XML.
2. **Implementar Suporte a Raias (Lanes) e Colaboração**:
   * **Identificar Lanes Ativas**: Varra todos os nós de fluxo que possuem a chave `lane`. Se houver pelo menos uma raia definida, habilite o modo de colaboração.
   * **Gerar a Colaboração global**:
     * Insira a tag `<bpmn:collaboration id="Collaboration_1">`.
     * Insira a tag de participante linkada ao processo principal: `<bpmn:participant id="Participant_1" processRef="Process_1" name="Organização" />`.
   * **Injetar a árvore de Raias (`<bpmn:laneSet>`) em `<bpmn:process>`**:
     * Agrupe os IDs de todos os nós (tasks, gateways, events) com base no valor de `"lane"`. Nós sem lane explicitada devem ir para uma raia padrão (ex: `"Geral"` ou o primeiro setor identificado).
     * Dentro de `<bpmn:process id="Process_1">`, declare o agrupamento:
       ```xml
       <bpmn:laneSet id="LaneSet_1">
         <bpmn:lane id="Lane_[NomeSimplificado]" name="[Nome da Lane]">
           <!-- Referências para cada nó pertencente a esta raia -->
           <bpmn:flowNodeRef>node_1</bpmn:flowNodeRef>
           <bpmn:flowNodeRef>node_2</bpmn:flowNodeRef>
         </bpmn:lane>
       </bpmn:laneSet>
       ```
3. **Ajustar Diagrama DI (Visual) para Colaboração e Lanes**:
   * O visualizador/planejador do diagrama (`bpmndi`) precisa renderizar visualmente a caixa do participante (Pool) e as divisões das raias (Lanes) utilizando as tags `<bpmndi:BPMNShape>` corretas com suas posições e limites:
     ```xml
     <bpmndi:BPMNShape id="Participant_1_di" bpmnElement="Participant_1" isHorizontal="true">
       <dc:Bounds x="50" y="50" width="1200" height="600" />
     </bpmndi:BPMNShape>
     <bpmndi:BPMNShape id="Lane_Suporte_di" bpmnElement="Lane_Suporte" isHorizontal="true">
       <dc:Bounds x="80" y="50" width="1170" height="300" />
     </bpmndi:BPMNShape>
     ```
   * As formas de tarefas especializadas (`userTask`, `serviceTask`) devem possuir a renderização visual correta suportada pelo `bpmn-js`.
4. **Evolução do Algoritmo de Auto-Layout para Swimlanes**:
   * Em `translator.py`, modifique a lógica do `compute_auto_layout` ou da função de posicionamento para atribuir coordenadas Y (no caso de raias horizontais) segmentadas para cada raia.
   * Exemplo: Cada raia ativa recebe uma faixa vertical de Y (ex: Raia 1 de `y=100` a `y=350`, Raia 2 de `y=400` a `y=650`). O algoritmo BFS posiciona os nós horizontalmente (coordenada X) para manter a ordem do fluxo, e verticalmente (coordenada Y) centralizado na faixa da sua respectiva raia.
5. **Retrocompatibilidade e Tratamento de Falhas (Fallbacks)**:
   * Garanta que fluxos antigos que não tenham as novas propriedades no JSON continuem sendo parseados de forma segura:
     * Caso nenhuma `lane` seja identificada, omita a colaboração e as tags de raias, mantendo o processo plano (flat) para manter compatibilidade total.
     * Caso a chave `task_type` não esteja definida para um nó com `cod_componente: 17`, utilize a tag padrão `<bpmn:task>`.
     * Caso a chave `event_type` não seja informada em eventos, renderize o evento básico correspondente sem as tags de gatilho adicionais.

---

### 3. Ajuste de Engenharia de Prompt (Gramática e Semântica)

* **Objetivo:** Garantir que a IA gere textos e nomes que estejam em conformidade com as boas práticas semânticas do BPMN.
* **Arquivos envolvidos:**
  * [backend/app.py](file:///c:/Users/Usuário/Documents/projetos/Nexus-Flow/backend/app.py)

#### 📝 Plano de Ação:
1. **Atualizar Prompt do Gerador Inteligente (`/generate-multimodal`)**:
   * Edite a constante `system_instruction` da rota.
   * Imponha que todas as instruções de geração de nós sigam regras rígidas de nomenclatura:
     * **Regra de Naming para Tasks**: Para componentes de ação (`cod_componente: 17`), o campo `"name"` deve obrigatoriamente começar com um verbo no infinitivo (ex: `"Verificar histórico"`, `"Enviar e-mail"`, `"Consultar saldo"`).
     * **Regra de Naming para Eventos**: Para componentes do tipo evento (início, fim ou intermediários como timer/mensagem), o campo `"name"` deve começar com um verbo no particípio (ex: `"Iniciado"`, `"Aguardado"`, `"Finalizado"`, `"Mensagem recebida"`).
   * Adicione exemplos claros no prompt para a IA aprender a estruturar as raias (`"lane"`) e os tipos de tarefas/eventos corretamente.
2. **Atualizar Prompt do Refinador Iterativo (`/refine-flow`)**:
   * Aplique as mesmas restrições e regras semânticas no prompt de sistema do refinamento para garantir que novas alterações continuem seguindo as regras gramaticais.

---

### 4. Geração de Testes Automatizados

* **Objetivo:** Garantir que as evoluções no esquema, no tradutor BPMN e nos prompts funcionem corretamente e não causem regressão.
* **Arquivos envolvidos:**
  * [backend/tests/test_translator.py](file:///c:/Users/Usuário/Documents/projetos/Nexus-Flow/backend/tests/test_translator.py)
  * [backend/tests/test_api.py](file:///c:/Users/Usuário/Documents/projetos/Nexus-Flow/backend/tests/test_api.py)

#### 📝 Plano de Ação:
1. **Atualizar `test_translator.py`**:
   * Adicione casos de teste que contenham as novas chaves: `lane`, `task_type` e `event_type`.
   * Valide se o XML gerado inclui a estrutura `<bpmn:collaboration>`, `<bpmn:laneSet>`, e se as tags `<bpmn:userTask>` e `<bpmn:timerEventDefinition />` estão presentes.
2. **Atualizar `test_api.py`**:
   * Crie testes enviando payloads JSON evoluídos para as rotas e garantindo que o backend valide e responda com o XML correto e status `200`.
