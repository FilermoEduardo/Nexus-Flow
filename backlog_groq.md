# Backlog: Integração do Llama 3.3 70B (Groq) no Nexus-Flow

Este documento descreve o passo a passo para integrar exclusivamente o modelo **Llama 3.3 70B Versatile** da **Groq** no projeto Nexus-Flow. Este modelo será utilizado tanto para o **Oráculo de Manutenção** quanto para o **Gerador Inteligente BPMN**.

---

## 🤖 Modelo Selecionado

* **Modelo:** **Llama 3.3 70B Versatile (`llama-3.3-70b-versatile`)**
* **Objetivo:** Garantir a máxima precisão lógica no diagnóstico de erros e manutenção (Oráculo) e evitar quebras de sintaxe/esquema ao gerar XML estruturado de BPMN (Gerador).

---

## 🛠️ Passo 1: Variáveis de Ambiente (`.env`)

Adicione a chave de acesso da Groq no seu arquivo `/backend/.env`:

```env
# Chave da Groq
GROQ_API_KEY=sua_chave_groq_aqui
```

---

## 📦 Passo 2: Dependências do Python (`backend/requirements.txt`)

Instale o SDK oficial da Groq. Adicione a linha abaixo ao arquivo de dependências:

```txt
groq>=0.9.0
```

E execute o comando de instalação:
```bash
pip install -r backend/requirements.txt
```

---

## 🧠 Passo 3: Modificações no Backend (`backend/app.py`)

### 3.1. Importação e Inicializador do Cliente
No topo de `backend/app.py`, adicione a importação do cliente Groq:

```python
from groq import Groq

_groq_client = None

def get_groq_client():
    global _groq_client
    api_key = os.environ.get("GROQ_API_KEY")
    if _groq_client is None:
        _groq_client = Groq(api_key=api_key)
    return _groq_client
```

### 3.2. Atualizar a Função `generate_llm_response`
Adicione o tratamento para a chamada do provedor `groq` com o modelo Llama 3.3 70B:

```python
def generate_llm_response(prompt, provider, model_name, attached_file=None, response_json=False, stream=False):
    # --- FLUXO LOCAL (FOUNDRY / OLLAMA) ---
    if provider in ("foundry", "ollama"):
        # ... (código existente) ...

    # --- FLUXO GROQ ---
    elif provider == "groq":
        client = get_groq_client()
        actual_model = "llama-3.3-70b-versatile"
        messages = [{"role": "user", "content": prompt}]
        
        response_format = {"type": "json_object"} if response_json else None
        
        if stream:
            def groq_stream_generator():
                completion = client.chat.completions.create(
                    model=actual_model,
                    messages=messages,
                    stream=True
                )
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': content}}]})}\n\n"
            return groq_stream_generator()
        else:
            completion = client.chat.completions.create(
                model=actual_model,
                messages=messages,
                response_format=response_format
            )
            return completion.choices[0].message.content

    # --- FLUXO GEMINI (PADRÃO) ---
    else:
        # ... (código existente) ...
```

### 3.3. Adicionar Verificação de Saúde no `/check-models`
Atualize o endpoint para testar a conectividade da chave da Groq com o Llama 3.3 70B:

```python
@app.route('/check-models', methods=['GET'])
def check_models():
    gemini_models = ['gemini-3.5-flash']
    groq_models = ['groq:llama-3.3-70b-versatile']
    
    results = {}
    
    # 1. Teste do Gemini existente
    # ...
    
    # 2. Teste da Groq
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        try:
            client = get_groq_client()
            client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            results['groq:llama-3.3-70b-versatile'] = {"available": True}
        except Exception as e:
            results['groq:llama-3.3-70b-versatile'] = {"available": False, "error": str(e)}
    else:
        results['groq:llama-3.3-70b-versatile'] = {"available": False, "error": "Chave ausente"}
        
    return jsonify(results), 200
```

---

## 🎨 Passo 4: Modificações no Frontend (`frontend/index.html`)

Adicione a opção do Llama 3.3 70B nos seletores de modelo do [index.html](file:///C:/Users/Usuário/Documents/projetos/Nexus-Flow/frontend/index.html):

```html
<select class="model-selector bg-transparent text-slate-200 text-xs font-medium outline-none cursor-pointer">
    <option value="gemini:gemini-3.5-flash" class="bg-slate-950 text-slate-200" selected>Gemini 3.5 Flash (Nuvem)</option>
    
    <!-- Novo modelo Groq -->
    <option value="groq:llama-3.3-70b-versatile" class="bg-slate-950 text-slate-200">Groq - Llama 3.3 70B (Nuvem)</option>
    
    <!-- Opções Locais existentes -->
    <option value="foundry:phi-3-mini-4k" class="bg-slate-950 text-slate-200">Phi-3 Mini (3B - Local)</option>
    <option value="foundry:qwen2.5-coder-7b" class="bg-slate-950 text-slate-200">Qwen 2.5 Coder (7B - Local)</option>
</select>
```
