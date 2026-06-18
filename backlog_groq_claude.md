# Backlog: Integração Multi-Provedores (Groq & Claude) no Nexus-Flow

Este documento descreve o passo a passo para integrar os provedores **Groq** e **Anthropic (Claude)** no projeto Nexus-Flow, permitindo o uso de múltiplas chaves de API além do Gemini.

---

## 🛠️ Passo 1: Variáveis de Ambiente (`.env`)

Adicione as novas chaves de API no seu arquivo `.env` localizado no diretório `/backend/.env`:

```env
# Chaves existentes
GEMINI_API_KEY=sua_chave_gemini

# Novas chaves de API
GROQ_API_KEY=sua_chave_groq
ANTHROPIC_API_KEY=sua_chave_claude
```

---

## 📦 Passo 2: Dependências do Python (`backend/requirements.txt`)

Instale os SDKs oficiais da Groq e da Anthropic. Adicione no arquivo de dependências:

```txt
groq>=0.9.0
anthropic>=0.18.0
```

E execute a instalação:
```bash
pip install -r backend/requirements.txt
```

---

## 🧠 Passo 3: Modificações no Backend (`backend/app.py`)

### 3.1. Importações e Inicialização dos Clientes
No topo de `backend/app.py`, importe as bibliotecas e crie funções de inicialização similares ao do Gemini:

```python
from groq import Groq
from anthropic import Anthropic

# Inicializadores globais
_groq_client = None
_anthropic_client = None

def get_groq_client():
    global _groq_client
    api_key = os.environ.get("GROQ_API_KEY")
    if _groq_client is None:
        _groq_client = Groq(api_key=api_key)
    return _groq_client

def get_anthropic_client():
    global _anthropic_client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=api_key)
    return _anthropic_client
```

### 3.2. Atualizar a Função `generate_llm_response`
Modifique a função para rotear requisições dos provedores `groq` e `claude`/`anthropic`:

```python
def generate_llm_response(prompt, provider, model_name, attached_file=None, response_json=False, stream=False):
    # --- FLUXO LOCAL (FOUNDRY / OLLAMA) ---
    if provider in ("foundry", "ollama"):
        # ... (código existente) ...

    # --- FLUXO CLAUDE (ANTHROPIC) ---
    elif provider in ("claude", "anthropic"):
        client = get_anthropic_client()
        
        # Mapeamento do modelo padrão do Claude
        actual_model = model_name if model_name else "claude-3-5-sonnet-20241022"
        
        # Estrutura básica de mensagens para Anthropic
        # Caso precise enviar anexos/imagens, utilize o formato de conteúdo estruturado do SDK
        messages = [{"role": "user", "content": prompt}]
        
        if stream:
            def claude_stream_generator():
                with client.messages.stream(
                    max_tokens=4096,
                    messages=messages,
                    model=actual_model,
                ) as stream_resp:
                    for text in stream_resp.text_stream:
                        yield f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n"
            return claude_stream_generator()
        else:
            response = client.messages.create(
                max_tokens=4096,
                messages=messages,
                model=actual_model,
            )
            return response.content[0].text

    # --- FLUXO GROQ ---
    elif provider == "groq":
        client = get_groq_client()
        
        actual_model = model_name if model_name else "llama-3.3-70b-versatile"
        messages = [{"role": "user", "content": prompt}]
        
        # Formato de resposta JSON caso solicitado
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
        # ... (código existente do Gemini) ...
```

### 3.3. Adicionar Verificação de Saúde dos Modelos (`/check-models`)
Atualize o endpoint de status para validar as chaves e conectividade do Groq e Claude:

```python
@app.route('/check-models', methods=['GET'])
def check_models():
    # Modelos a serem testados
    gemini_models = ['gemini-3.5-flash']
    groq_models = ['groq:llama-3.3-70b-versatile']
    claude_models = ['claude:claude-3-5-sonnet-20241022']
    
    results = {}
    
    # 1. Testar Gemini (código existente)
    # ...
    
    # 2. Testar Groq
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

    # 3. Testar Claude
    claude_key = os.environ.get("ANTHROPIC_API_KEY")
    if claude_key:
        try:
            client = get_anthropic_client()
            client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
            results['claude:claude-3-5-sonnet-20241022'] = {"available": True}
        except Exception as e:
            results['claude:claude-3-5-sonnet-20241022'] = {"available": False, "error": str(e)}
    else:
        results['claude:claude-3-5-sonnet-20241022'] = {"available": False, "error": "Chave ausente"}
        
    return jsonify(results), 200
```

---

## 🎨 Passo 4: Modificações no Frontend (`frontend/index.html`)

Adicione as opções de modelos do Groq e Claude nos seletores `<select class="model-selector">` presentes nas telas do **Oráculo de Manutenção** e do **Gerador Inteligente BPMN**:

```html
<select class="model-selector bg-transparent text-slate-200 text-xs font-medium outline-none cursor-pointer">
    <option value="gemini:gemini-3.5-flash" class="bg-slate-950 text-slate-200" selected>Gemini 3.5 Flash (Nuvem)</option>
    <!-- Opções locais existentes -->
    <option value="foundry:phi-3-mini-4k" class="bg-slate-950 text-slate-200">Phi-3 Mini (3B - Local)</option>
    <option value="foundry:qwen2.5-coder-7b" class="bg-slate-950 text-slate-200">Qwen 2.5 Coder (7B - Local)</option>
    
    <!-- Novos Modelos em Nuvem -->
    <option value="groq:llama-3.3-70b-versatile" class="bg-slate-950 text-slate-200">Groq - Llama 3.3 (70B - Nuvem)</option>
    <option value="claude:claude-3-5-sonnet-20241022" class="bg-slate-950 text-slate-200">Claude 3.5 Sonnet (Nuvem)</option>
</select>
```

---

## 🧪 Passo 5: Testar o Sistema

1. **Ative o ambiente virtual** do backend e inicie o servidor:
   ```bash
   python backend/app.py
   ```
2. Abra a interface web, selecione **Groq** ou **Claude** no seletor de IA no cabeçalho e faça uma pergunta técnica ou envie um fluxo para validação.
3. Monitore o console do Flask para garantir que a rota correta está mapeando o provedor (`X-Provider-Model`).
