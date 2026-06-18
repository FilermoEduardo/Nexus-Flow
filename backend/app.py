# pyrefly: ignore [missing-import]
import os
import json
import base64
import requests
import traceback
import time
from functools import wraps
# pyrefly: ignore [missing-import]
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
from google import genai
from google.genai import types
from translator import generate_bpmn_xml
from drawio_parser import parse_drawio_to_json
from jsonschema import validate, ValidationError
# pyrefly: ignore [missing-import]
from flask_limiter import Limiter
# pyrefly: ignore [missing-import]
from flask_limiter.util import get_remote_address

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv(override=True)

_gemini_client = None
_last_api_key = None

def get_gemini_client(api_key=None):
    global _gemini_client, _last_api_key
    if api_key is None:
        api_key = os.environ.get("GEMINI_API_KEY")
    if _gemini_client is None or _last_api_key != api_key:
        _gemini_client = genai.Client(api_key=api_key)
        _last_api_key = api_key
    return _gemini_client

from groq import Groq

_groq_client = None

def get_groq_client():
    global _groq_client
    api_key = os.environ.get("GROQ_API_KEY")
    if _groq_client is None:
        _groq_client = Groq(api_key=api_key)
    return _groq_client

app = Flask(__name__)
CORS(app)

# Configura o Rate Limiter (Melhoria 6)
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["300 per day", "100 per hour"],
    storage_uri="memory://"
)

# Schema de validação para fluxos Estella JSON (Melhoria 5)
FLOW_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": ["integer", "string"]},
            "parent": {"type": ["integer", "string", "null"]},
            "edge": {"type": "integer"},
            "cod_componente": {"type": ["integer", "string", "null"]},
            "name": {"type": "string"},
            "source": {"type": ["integer", "string"]},
            "target": {"type": ["integer", "string"]},
            "value": {"type": "string"},
            "lane": {"type": "string"},
            "task_type": {"type": "string", "enum": ["user", "service", "manual", "script", "send", "receive"]},
            "event_type": {"type": "string", "enum": ["timer", "error", "terminate", "message"]}
        },
        "required": ["id"]
    }
}

def require_api_key(f):
    """
    Decorador para autenticação via token no header (Melhoria 6).
    Se APP_API_TOKEN estiver definido nas variáveis de ambiente, exige sua validação.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        expected_token = os.environ.get("APP_API_TOKEN")
        if expected_token:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return jsonify({"error": "Token de autorização ausente ou inválido."}), 401
            token = auth_header.split(" ")[1]
            if token != expected_token:
                return jsonify({"error": "Acesso não autorizado. Token inválido."}), 401
        return f(*args, **kwargs)
    return decorated

def extract_json(text):
    """
    Extrai e limpa blocos JSON de strings retornadas pela IA,
    removendo marcações de markdown se houver.
    """
    text = text.strip()
    if not text:
        return ""
    
    # Se já começar com [ ou {, tenta parsear direto
    if text.startswith('{') or text.startswith('['):
        return text
        
    # Tenta encontrar blocos delimitados por ```json ... ```
    import re
    match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if match:
        return match.group(1).strip()
        
    # Tenta encontrar blocos genéricos de ``` ... ```
    match = re.search(r'```\s*([\s\S]*?)\s*```', text)
    if match:
        return match.group(1).strip()
        
    # Se não houver blocos marcados, tenta encontrar do primeiro { ou [ até o último } ou ]
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    first_bracket = text.find('[')
    last_bracket = text.rfind(']')
    
    if first_brace != -1 and last_brace != -1:
        if first_bracket != -1 and first_bracket < first_brace and last_bracket > last_brace:
            return text[first_bracket:last_bracket+1].strip()
        return text[first_brace:last_brace+1].strip()
        
    if first_bracket != -1 and last_bracket != -1:
        return text[first_bracket:last_bracket+1].strip()
        
    return text

def compact_flow_for_prompt(flow_data):
    """
    Compacta o fluxo de dados em uma representação legível e ultra-enxuta,
    reduzindo o consumo de tokens em mais de 90%.
    """
    if not isinstance(flow_data, list):
        return ""
    
    nodes = []
    edges = []
    
    for item in flow_data:
        is_edge = item.get("edge") == 1 or "source" in item
        if is_edge:
            source = item.get("source")
            target = item.get("target")
            val = item.get("value")
            if source is not None and target is not None:
                edge_str = f"{source}->{target}"
                if val:
                    edge_str += f"('{val}')"
                edges.append(edge_str)
        else:
            nid = item.get("id")
            name = item.get("name", "")
            cod = item.get("cod_componente")
            lane = item.get("lane")
            task_type = item.get("task_type")
            event_type = item.get("event_type")
            
            node_desc = f"ID {nid}: '{name}'"
            props = []
            if cod is not None:
                props.append(f"t:{cod}")
            if lane:
                props.append(f"r:{lane}")
            if task_type:
                props.append(f"tt:{task_type}")
            if event_type:
                props.append(f"et:{event_type}")
            
            if props:
                node_desc += " (" + ",".join(props) + ")"
            nodes.append(node_desc)
            
    return "Nós:\n" + "\n".join(nodes) + "\n\nConexões:\n" + ",".join(edges)

def generate_llm_response(prompt, provider, model_name, attached_file=None, response_json=False, stream=False):
    """
    Função unificada para gerar conteúdo usando Gemini (nuvem) ou Foundry Local (local),
    com suporte para streaming de respostas (Melhoria 2).
    """
    if provider in ("foundry", "ollama"):
        # Mapeamento do endpoint do Foundry Local
        foundry_api_base = os.environ.get("FOUNDRY_API_BASE", "http://localhost:8080/v1")
        url = f"{foundry_api_base}/chat/completions"
        
        # Obter a porta configurada no FOUNDRY_API_BASE
        import urllib.parse
        parsed_url = urllib.parse.urlparse(foundry_api_base)
        port_info = f" na porta {parsed_url.port}" if parsed_url.port else ""
        
        # Obter modelos disponíveis no Foundry Local para mapeamento dinâmico
        try:
            models_resp = requests.get(f"{foundry_api_base}/models", timeout=5)
            if models_resp.status_code == 200:
                available_models = [m.get("id") for m in models_resp.json().get("data", [])]
            else:
                available_models = []
        except Exception:
            available_models = []

        actual_model = model_name
        matched_model = None
        if available_models:
            search_term = model_name.lower()
            if "qwen" in search_term and "coder" in search_term:
                matched_model = next((m for m in available_models if "qwen" in m.lower() and "coder" in m.lower()), None)
            elif "phi" in search_term or "mini" in search_term:
                matched_model = next((m for m in available_models if "phi" in m.lower() and ("3" in m.lower() or "mini" in m.lower())), None)
            
            if matched_model:
                actual_model = matched_model
                
        if not matched_model:
            # Fallback robusto caso a consulta de modelos falhe ou não encontre correspondente
            if "qwen" in actual_model.lower():
                actual_model = "qwen2.5-coder-7b-instruct-openvino-gpu:2"
            elif "llama" in actual_model.lower():
                actual_model = "qwen2.5-coder-7b-instruct-openvino-gpu:2"
            elif "phi" in actual_model.lower() or "pi" in actual_model.lower():
                actual_model = "Phi-3-mini-4k-instruct-openvino-gpu:2"
            
        # Preparação das mensagens compatíveis com OpenAI
        if attached_file and "image" in (attached_file.content_type or ""):
            attached_file.seek(0)
            file_bytes = attached_file.read()
            b64_img = base64.b64encode(file_bytes).decode('utf-8')
            mime_type = attached_file.content_type or "image/jpeg"
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}}
                ]
            }]
        else:
            messages = [{"role": "user", "content": prompt}]
            
        payload = {
            "model": actual_model,
            "messages": messages,
            "stream": stream,
            "max_tokens": 4096
        }
        
        if response_json:
            payload["response_format"] = {"type": "json_object"}
            
        if stream:
            # Gerador para streaming do Foundry Local (formato SSE compatível com OpenAI)
            def foundry_stream_generator():
                try:
                    response = requests.post(url, json=payload, timeout=600, stream=True)
                    response.raise_for_status()
                except requests.exceptions.ConnectionError as ce:
                    raise RuntimeError(
                        f"Não foi possível conectar ao Foundry Local. Certifique-se de que o serviço do Foundry está rodando (execute 'foundry service start' no terminal{port_info})."
                    ) from ce
                except requests.exceptions.HTTPError as he:
                    try:
                        err_json = he.response.json()
                        err_msg = err_json.get("error", {}).get("message", str(he))
                    except Exception:
                        err_msg = he.response.text or str(he)
                    
                    if "not found" in err_msg.lower() or "no model" in err_msg.lower():
                        raise RuntimeError(
                            f"O modelo '{actual_model}' não foi encontrado no Foundry Local. Execute o comando 'foundry model download {actual_model}' no seu terminal para baixá-lo."
                        ) from he
                    raise RuntimeError(f"Erro retornado pelo Foundry Local: {err_msg}") from he
                except Exception as e:
                    raise RuntimeError(f"Erro inesperado ao conectar ao Foundry Local: {str(e)}") from e

                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8').strip()
                        if decoded_line.startswith("data:"):
                            content_str = decoded_line[5:].strip()
                            if content_str == "[DONE]":
                                break
                            try:
                                res_data = json.loads(content_str)
                                token = res_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if token:
                                    yield token
                            except Exception:
                                pass
            return foundry_stream_generator()
        else:
            # Chamada convencional síncrona
            try:
                response = requests.post(url, json=payload, timeout=600)
                response.raise_for_status()
                res_data = response.json()
                return res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            except requests.exceptions.ConnectionError as ce:
                raise RuntimeError(
                    f"Não foi possível conectar ao Foundry Local. Certifique-se de que o serviço do Foundry está rodando (execute 'foundry service start' no terminal{port_info})."
                ) from ce
            except requests.exceptions.HTTPError as he:
                try:
                    err_json = he.response.json()
                    err_msg = err_json.get("error", {}).get("message", str(he))
                except Exception:
                    err_msg = he.response.text or str(he)
                
                if "not found" in err_msg.lower() or "no model" in err_msg.lower():
                    raise RuntimeError(
                        f"O modelo '{actual_model}' não foi encontrado no Foundry Local. Execute o comando 'foundry model download {actual_model}' no seu terminal para baixá-lo."
                    ) from he
                raise RuntimeError(f"Erro retornado pelo Foundry Local: {err_msg}") from he
            except Exception as e:
                raise RuntimeError(f"Erro inesperado ao conectar ao Foundry Local: {str(e)}") from e
    elif provider == "groq":
        load_dotenv(override=True)
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("Chave de API da Groq (GROQ_API_KEY) não configurada no arquivo .env.")
        client = get_groq_client()
        
        actual_model = "llama-3.3-70b-versatile"
        messages = [{"role": "user", "content": prompt}]
        
        response_format = {"type": "json_object"} if response_json else None
        
        if stream:
            def groq_stream_generator():
                completion = client.chat.completions.create(
                    model=actual_model,
                    messages=messages,
                    stream=True,
                    response_format=response_format
                )
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield content
            return groq_stream_generator()
        else:
            completion = client.chat.completions.create(
                model=actual_model,
                messages=messages,
                response_format=response_format
            )
            return completion.choices[0].message.content
    else:
        # Carrega e configura o Gemini dinamicamente a cada requisição
        load_dotenv(override=True)
        api_key = os.environ.get("GEMINI_API_KEY")
        client = get_gemini_client(api_key)

        # Chamada ao Gemini na nuvem (Padrão)
        actual_model = model_name
        # Mapeamento dinâmico para os modelos mais novos
        if "3.5-flash" in model_name:
            actual_model = "gemini-2.5-flash"
        elif "3.5-pro" in model_name:
            actual_model = "gemini-2.5-pro"
            
        contents = []
        if attached_file:
            attached_file.seek(0)
            file_bytes = attached_file.read()
            contents.append(
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=attached_file.content_type
                )
            )
        contents.append(prompt)
        
        config = types.GenerateContentConfig()
        if response_json:
            config.response_mime_type = "application/json"
            
        # Tentativa de chamada com backoff exponencial contra timeouts temporários (504)
        for attempt in range(3):
            try:
                if stream:
                    res = client.models.generate_content_stream(
                        model=actual_model,
                        contents=contents,
                        config=config
                    )
                    # Gerador para streaming do Gemini
                    def gemini_stream_generator():
                        for chunk in res:
                            if chunk.text:
                                yield chunk.text
                    return gemini_stream_generator()
                else:
                    res = client.models.generate_content(
                        model=actual_model,
                        contents=contents,
                        config=config
                    )
                    return res.text
            except Exception as ex:
                if attempt == 2:
                    raise ex
                time.sleep(2 ** attempt)

@app.route('/upload', methods=['POST'])
@require_api_key
def upload_file():
    try:
        data = request.get_json(force=True)
        if not data or 'flow' not in data or not isinstance(data['flow'], list):
            raise ValueError("Estrutura do fluxo inválida")
            
        flow_data = data['flow']
        
        # Validar Schema JSON (Melhoria 5)
        try:
            validate(instance=flow_data, schema=FLOW_SCHEMA)
        except ValidationError as ve:
            return jsonify({"error": f"Schema do fluxo inválido: {ve.message}"}), 400

        auto_layout = request.args.get('auto_layout', 'false').lower() == 'true' or data.get('auto_layout', False)
        xml_output = generate_bpmn_xml(flow_data, auto_layout=auto_layout)
        
        return xml_output, 200, {'Content-Type': 'application/xml'}
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro Interno: {str(e)}"}), 400

@app.route('/convert-drawio', methods=['POST'])
@require_api_key
def convert_drawio():
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "Nenhum arquivo enviado."}), 400
            
        content = file.read().decode('utf-8', errors='ignore')
        result_json = parse_drawio_to_json(content)
        
        # Validar Schema JSON do resultado da conversão para garantir integridade
        if "flow" in result_json:
            try:
                validate(instance=result_json["flow"], schema=FLOW_SCHEMA)
            except ValidationError as ve:
                print(f"[Aviso] O XML convertido gerou um JSON fora do schema: {ve.message}")
        
        return jsonify(result_json), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro na conversão: {str(e)}"}), 500

@app.route('/chat', methods=['POST'])
@require_api_key
@limiter.limit("15 per minute")
def chat():
    try:
        # Suportar tanto Multipart Form (para arquivos) quanto JSON cru
        is_multipart = request.content_type and 'multipart/form-data' in request.content_type
        
        if is_multipart:
            question = request.form.get('question')
            flow_data_raw = request.form.get('flow_data', '[]')
            try:
                flow_data = json.loads(flow_data_raw)
            except Exception:
                flow_data = []
            attached_file = request.files.get('file')
        else:
            data = request.get_json(force=True)
            if not data or 'question' not in data:
                return jsonify({"error": "Parâmetro 'question' é obrigatório."}), 400
            question = data.get('question')
            flow_data = data.get('flow_data', [])
            attached_file = None

        if not question:
            return jsonify({"error": "A pergunta não pode estar vazia."}), 400

        # Validar Schema JSON (Melhoria 5)
        if flow_data:
            try:
                validate(instance=flow_data, schema=FLOW_SCHEMA)
            except ValidationError as ve:
                return jsonify({"error": f"Schema do fluxo inválido: {ve.message}"}), 400

        # Obtém o motor de IA do header (ex: "gemini:gemini-2.5-flash" ou "ollama:qwen2.5:3b")
        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-3.5-flash')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-3.5-flash'

        # Compacta o fluxo para economizar tokens e evitar estouros de TPD/TPM
        flow_representation = compact_flow_for_prompt(flow_data)
        
        system_instruction = (
            "Você é um Especialista em UX Conversacional e Arquiteto de Soluções de Chatbot. "
            "Sua tarefa é analisar a estrutura do fluxo de dados do chatbot legado e auxiliar a equipe de manutenção.\n\n"
            "🚨 REGRA DE OURO PARA RESPOSTAS:\n"
            "1. Se o usuário fizer uma pergunta ESPECÍFICA (ex: 'Liste as APIs', 'Onde está a troca de senha?', 'O que o nó 14 faz?'), "
            "vá DIRETO AO PONTO. Responda APENAS o que foi perguntado, de forma concisa e técnica, SEM usar a estrutura de documentação completa.\n"
            "2. APENAS se o usuário pedir uma explicação GERAL, um resumo do fluxo, ou a documentação completa, "
            "você deve organizar sua resposta usando a seguinte estrutura didática:\n\n"
            "   - **Resumo do Fluxo**: A finalidade principal deste fluxograma.\n"
            "   - **Jornada do Usuário**: O caminho de ponta a ponta, com IDs de referência (ex: ID: 15).\n"
            "   - **Decisões e Bifurcações**: Regras de decisão e caminhos.\n"
            "   - **Ações Especiais**: Integrações de API e Scripts.\n\n"
            "Mantenha sempre um tom profissional e use Markdown para formatar listas e negritos de forma limpa."
        )
        
        prompt = (
            f"{system_instruction}\n\n"
            f"Estrutura do fluxo:\n{flow_representation}\n\n"
            f"Pergunta do usuário: {question}\n\n"
            f"ATENÇÃO: Responda obrigatoriamente em português do Brasil (pt-BR). Não escreva em inglês em hipótese alguma."
        )
        
        # Chama a função unificada
        response_text = generate_llm_response(
            prompt=prompt,
            provider=provider,
            model_name=model_name,
            attached_file=attached_file,
            response_json=False
        )
            
        return jsonify({"response": response_text}), 200
        
    except Exception as e:
        traceback.print_exc()
        err_msg = str(e)
        if "429" in err_msg or "quota" in err_msg.lower() or "ResourceExhausted" in err_msg:
            import re
            retry_match = re.search(r"Please retry in ([\d\.]+)s", err_msg)
            retry_after = float(retry_match.group(1)) if retry_match else 10.0
            quota_type = "day" if "PerDay" in err_msg or "day" in err_msg.lower() else "minute"
            return jsonify({
                "error": "Você atingiu o limite de requisições do Oraculo. Por favor, aguarde ou use um modelo local.",
                "retry_after": retry_after,
                "quota_type": quota_type,
                "model": model_name
            }), 429
            
        return jsonify({"error": f"Erro no Oráculo: {err_msg}"}), 500

@app.route('/chat-stream', methods=['POST'])
@require_api_key
@limiter.limit("15 per minute")
def chat_stream():
    """
    Rota de chat com suporte a Streaming via Server-Sent Events (Melhoria 2).
    """
    try:
        is_multipart = request.content_type and 'multipart/form-data' in request.content_type
        
        if is_multipart:
            question = request.form.get('question')
            flow_data_raw = request.form.get('flow_data', '[]')
            try:
                flow_data = json.loads(flow_data_raw)
            except Exception:
                flow_data = []
            attached_file = request.files.get('file')
        else:
            data = request.get_json(force=True)
            if not data or 'question' not in data:
                return jsonify({"error": "Parâmetro 'question' é obrigatório."}), 400
            question = data.get('question')
            flow_data = data.get('flow_data', [])
            attached_file = None

        if not question:
            return jsonify({"error": "A pergunta não pode estar vazia."}), 400

        # Validar Schema JSON
        if flow_data:
            try:
                validate(instance=flow_data, schema=FLOW_SCHEMA)
            except ValidationError as ve:
                return jsonify({"error": f"Schema do fluxo inválido: {ve.message}"}), 400

        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-3.5-flash')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-3.5-flash'

        # Compacta o fluxo para economizar tokens e evitar estouros de TPD/TPM
        flow_representation = compact_flow_for_prompt(flow_data)
        
        system_instruction = (
            "Você é um Especialista em UX Conversacional e Arquiteto de Soluções de Chatbot. "
            "Sua tarefa é analisar a estrutura do fluxo de dados do chatbot legado e auxiliar a equipe de manutenção.\n\n"
            "🚨 REGRA DE OURO PARA RESPOSTAS:\n"
            "1. Se o usuário fizer uma pergunta ESPECÍFICA (ex: 'Liste as APIs', 'Onde está a troca de senha?', 'O que o nó 14 faz?'), "
            "vá DIRETO AO PONTO. Responda APENAS o que foi perguntado, de forma concisa e técnica, SEM usar a estrutura de documentação completa.\n"
            "2. APENAS se o usuário pedir uma explicação GERAL, um resumo do fluxo, ou a documentação completa, "
            "você deve organizar sua resposta usando a seguinte estrutura didática:\n\n"
            "   - **Resumo do Fluxo**: A finalidade principal deste fluxograma.\n"
            "   - **Jornada do Usuário**: O caminho de ponta a ponta, com IDs de referência (ex: ID: 15).\n"
            "   - **Decisões e Bifurcações**: Regras de decisão e caminhos.\n"
            "   - **Ações Especiais**: Integrações de API e Scripts.\n\n"
            "Mantenha sempre um tom profissional e use Markdown para formatar listas e negritos de forma limpa."
        )
        
        prompt = (
            f"{system_instruction}\n\n"
            f"Estrutura do fluxo:\n{flow_representation}\n\n"
            f"Pergunta do usuário: {question}\n\n"
            f"ATENÇÃO: Responda obrigatoriamente em português do Brasil (pt-BR). Não escreva em inglês em hipótese alguma."
        )
        
        # Inicia o gerador de streaming
        stream_generator = generate_llm_response(
            prompt=prompt,
            provider=provider,
            model_name=model_name,
            attached_file=attached_file,
            response_json=False,
            stream=True
        )

        def event_stream():
            try:
                for token in stream_generator:
                    yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "quota" in err_msg.lower() or "ResourceExhausted" in err_msg:
                    import re
                    retry_match = re.search(r"Please retry in ([\d\.]+)s", err_msg)
                    retry_after = float(retry_match.group(1)) if retry_match else 10.0
                    quota_type = "day" if "PerDay" in err_msg or "day" in err_msg.lower() else "minute"
                    yield f"data: {json.dumps({'error': err_msg, 'retry_after': retry_after, 'quota_type': quota_type, 'model': model_name})}\n\n"
                else:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(event_stream(), mimetype='text/event-stream')

    except Exception as e:
        traceback.print_exc()
        err_msg = str(e)
        if "429" in err_msg or "quota" in err_msg.lower() or "ResourceExhausted" in err_msg:
            import re
            retry_match = re.search(r"Please retry in ([\d\.]+)s", err_msg)
            retry_after = float(retry_match.group(1)) if retry_match else 10.0
            quota_type = "day" if "PerDay" in err_msg or "day" in err_msg.lower() else "minute"
            return jsonify({
                "error": "Erro de stream: cota excedida.",
                "retry_after": retry_after,
                "quota_type": quota_type,
                "model": model_name
            }), 429
        return jsonify({"error": f"Erro de stream: {str(e)}"}), 500

@app.route('/generate-multimodal', methods=['POST'])
@require_api_key
@limiter.limit("10 per minute")
def generate_multimodal():
    try:
        # Pega a descrição de texto se houver
        question = request.form.get('description', '')
        
        # Pega o arquivo de mídia se houver
        attached_file = request.files.get('file')
        
        if not question and not attached_file:
            return jsonify({"error": "Forneça uma descrição em texto ou envie um arquivo de áudio/imagem/PDF."}), 400

        # Obtém o motor de IA do header (ex: "gemini:gemini-2.5-flash" ou "ollama:qwen2.5:3b")
        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-3.5-flash')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-3.5-flash'
            
        system_instruction = (
            "Você é um arquiteto especialista em Chatbots e engenharia de processos BPMN 2.0. "
            "Sua tarefa é analisar a descrição enviada (seja em áudio, imagem, PDF ou texto) e convertê-la estruturalmente em um fluxo de atendimento para chatbot. "
            "Você deve retornar a resposta estritamente em formato JSON no esquema detalhado abaixo.\n\n"
            "🚨 DIRETRIZ DE DETALHAMENTO (NÃO SIMPLIFICAR / COMPREENSIVIDADE):\n"
            "- Não simplifique, resuma ou omita etapas da descrição do usuário. Cada ação, mensagem, decisão, checagem, validação, chamada de API e script citado deve virar um nó no fluxo JSON.\n"
            "- Se o usuário citar IDs específicos (ex: ID: 13, ID: 49), mapeie exatamente esse valor no campo \"id\" do nó correspondente para manter rastreabilidade.\n"
            "- Modele todas as ramificações de sucesso e caminhos alternativos/tratamentos de erro detalhadamente.\n\n"
            "REGRAS DE ESTRUTURA DO JSON:\n"
            "1. Nós (Nós de Atividade/Evento/Decisão):\n"
            "   - \"id\": ID inteiro incremental único (ex: 1, 2, 3).\n"
            "   - \"parent\": ID do nó imediatamente anterior no fluxo principal. O nó de início (Start Event) deve ter parent = null.\n"
            "   - \"edge\": 0 (indica que é um nó).\n"
            "   - \"cod_componente\": 1 para Início/Fim do fluxo (Eventos), 15 para Gateways de decisão/bifurcações, 9 para requisições de API/HTTP, 19 para scripts de processamento local, 17 para caixas de mensagens ou ações comuns (Tasks).\n"
            "   - \"name\": Nome resumido do nó (deve seguir as Regras Gramaticais de nomeação abaixo).\n"
            "   - \"lane\": Nome do papel, setor ou ator responsável (ex: 'Cliente', 'Suporte Técnico', 'Sistema'). Se usar raias, classifique TODOS os nós do fluxo nas raias correspondentes.\n"
            "   - \"task_type\" (obrigatório apenas para cod_componente: 17): Classificação técnica da tarefa. Valores aceitos: user (ação humana), service (chamada de API/serviço), manual (atividade fora do sistema), script (cálculo/script local), send (envio de mensagem ativa), receive (espera de entrada/mensagem).\n"
            "   - \"event_type\" (obrigatório apenas para eventos, cod_componente: 1 ou 11): Classificação técnica do evento. Valores aceitos: timer (tempo/timeout), error (fluxo de erro), terminate (fim total do processo), message (recebimento de mensagem externa).\n\n"
            "2. Conexões/Setas (Edges):\n"
            "   - \"id\": ID string único (ex: 'edge_1').\n"
            "   - \"edge\": 1 (indica que é uma conexão).\n"
            "   - \"source\": ID do nó de origem da conexão.\n"
            "   - \"target\": ID do nó de destino da conexão.\n"
            "   - \"value\": Condição ou rótulo do caminho (ex: 'Sim', 'Não', 'Opção 1', 'Sucesso'). Deve ser vazio para fluxos diretos.\n\n"
            "🚨 REGRAS DE RAMIFICAÇÃO (GATEWAYS):\n"
            "- Para criar bifurcações/decisões, utilize um nó de Gateway ('cod_componente': 15).\n"
            "- O gateway deve ter múltiplas conexões de saída (edges onde 'source' é o ID do gateway, apontando para diferentes nós 'target'). Cada uma dessas conexões deve possuir seu respectivo 'value' descrevendo o caminho da ramificação (ex: 'Sim' na conexão para o nó A, e 'Não' na conexão para o nó B).\n"
            "- Para fundir caminhos alternativos que se reúnem (convergência/merge), crie conexões (edges) dos últimos nós de cada caminho de volta para o mesmo nó de destino comum.\n\n"
            "🚨 REGRAS GRAMATICAIS E SEMÂNTICAS DE NOMEAÇÃO:\n"
            "1. **Para Tarefas/Ações** (cod_componente: 17, 9, 19): o campo 'name' deve OBRIGATORIAMENTE começar com um verbo no infinitivo (ex: 'Enviar mensagem', 'Verificar histórico', 'Solicitar dados').\n"
            "2. **Para Eventos** (início, fim ou intermediários, cod_componente: 1 ou 11): o campo 'name' deve OBRIGATORIAMENTE começar com um verbo no particípio (ex: 'Iniciado atendimento', 'Finalizado com sucesso', 'Aguardado timeout').\n\n"
            "Exemplo de JSON estruturado e ramificado esperado:\n"
            "{\n"
            "  \"flow\": [\n"
            "    { \"id\": 1, \"parent\": null, \"edge\": 0, \"cod_componente\": 1, \"lane\": \"Cliente\", \"name\": \"Iniciado atendimento\" },\n"
            "    { \"id\": 2, \"parent\": 1, \"edge\": 0, \"cod_componente\": 17, \"task_type\": \"user\", \"lane\": \"Cliente\", \"name\": \"Fornecer CPF\" },\n"
            "    { \"id\": 3, \"parent\": 2, \"edge\": 0, \"cod_componente\": 17, \"task_type\": \"service\", \"lane\": \"Sistema\", \"name\": \"Validar cadastro\" },\n"
            "    { \"id\": 4, \"parent\": 3, \"edge\": 0, \"cod_componente\": 15, \"lane\": \"Sistema\", \"name\": \"Verificar resultado da validação\" },\n"
            "    { \"id\": 5, \"parent\": 4, \"edge\": 0, \"cod_componente\": 17, \"task_type\": \"send\", \"lane\": \"Sistema\", \"name\": \"Apresentar menu principal\" },\n"
            "    { \"id\": 6, \"parent\": 4, \"edge\": 0, \"cod_componente\": 1, \"event_type\": \"error\", \"lane\": \"Sistema\", \"name\": \"Finalizado com erro\" },\n"
            "    { \"id\": \"edge_1\", \"edge\": 1, \"source\": 4, \"target\": 5, \"value\": \"Sucesso\" },\n"
            "    { \"id\": \"edge_2\", \"edge\": 1, \"source\": 4, \"target\": 6, \"value\": \"Falha\" }\n"
            "  ]\n"
            "}\n\n"
            "Gere apenas o JSON puro, sem blocos de código markdown ou texto explicativo extra."
        )
        
        prompt = f"{system_instruction}\n\nEntrada de texto descritivo do usuário (se fornecida): {question}"
        
        # Chama a função unificada
        response_text = generate_llm_response(
            prompt=prompt,
            provider=provider,
            model_name=model_name,
            attached_file=attached_file,
            response_json=True
        )
            
        if not response_text or not response_text.strip():
            raise RuntimeError("Não foi possível obter uma resposta válida do provedor de IA (a resposta está vazia).")
            
        # Parseia o JSON retornado de forma robusta extraindo blocos markdown se existirem
        try:
            cleaned_json = extract_json(response_text)
            flow_json = json.loads(cleaned_json)
        except json.JSONDecodeError as jde:
            print("--- ERRO DE DECODE NO GENERATE_MULTIMODAL ---")
            print(f"Response Text recebido: {repr(response_text)}")
            print(f"Cleaned JSON tentado: {repr(cleaned_json)}")
            print("---------------------------------------------")
            raise RuntimeError(
                f"A resposta gerada pela IA não pôde ser parseada como JSON estruturado válido.\n"
                f"Detalhes: {jde}\n"
                f"Resposta bruta da IA: {response_text}"
            ) from jde
        
        if 'flow' not in flow_json or not isinstance(flow_json['flow'], list):
            raise ValueError("O formato de fluxo gerado pela IA é inválido.")
            
        # Validar Schema JSON
        try:
            validate(instance=flow_json['flow'], schema=FLOW_SCHEMA)
        except ValidationError as ve:
            return jsonify({"error": f"Schema do fluxo gerado pela IA é inválido: {ve.message}"}), 400

        # Converte o fluxo gerado pela IA em XML BPMN 2.0 com auto_layout ativado
        xml_output = generate_bpmn_xml(flow_json['flow'], auto_layout=True)
        
        return xml_output, 200, {
            'Content-Type': 'application/xml',
            'Content-Disposition': 'attachment; filename=fluxo_gerado.bpmn',
            'Access-Control-Expose-Headers': 'X-Flow-JSON',
            'X-Flow-JSON': json.dumps(flow_json['flow'], ensure_ascii=False)
        }
        
    except Exception as e:
        traceback.print_exc()
        err_msg = str(e)
        if "429" in err_msg or "quota" in err_msg.lower() or "ResourceExhausted" in err_msg:
            import re
            retry_match = re.search(r"Please retry in ([\d\.]+)s", err_msg)
            retry_after = float(retry_match.group(1)) if retry_match else 10.0
            quota_type = "day" if "PerDay" in err_msg or "day" in err_msg.lower() else "minute"
            
            return jsonify({
                "error": "Você atingiu a cota limite de requisições gratuitas do Gemini. Por favor, aguarde alguns segundos ou use um modelo local.",
                "retry_after": retry_after,
                "quota_type": quota_type,
                "model": model_name
            }), 429
        return jsonify({"error": f"Erro na geração inteligente: {str(e)}"}), 500

@app.route('/refine-flow', methods=['POST'])
@require_api_key
@limiter.limit("10 per minute")
def refine_flow():
    """
    Rota para refinamento iterativo de fluxos BPMN (Melhoria 4).
    Recebe o JSON do fluxo existente e a instrução textual de modificação.
    Retorna o novo JSON modificado e o respectivo XML do BPMN 2.0 traduzido.
    """
    try:
        data = request.get_json(force=True)
        if not data or 'flow' not in data or 'instruction' not in data:
            return jsonify({"error": "Parâmetros 'flow' e 'instruction' são obrigatórios."}), 400
        
        flow_data = data['flow']
        instruction = data['instruction']
        
        # Validar Schema JSON
        try:
            validate(instance=flow_data, schema=FLOW_SCHEMA)
        except ValidationError as ve:
            return jsonify({"error": f"Schema do fluxo inválido: {ve.message}"}), 400
            
        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-3.5-flash')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-3.5-flash'
        
        system_instruction = (
            "Você é um arquiteto especialista em Chatbots e engenharia de processos BPMN 2.0.\n"
            "Sua tarefa é receber o JSON de um fluxo de chatbot existente e uma instrução de refinamento/modificação do usuário.\n"
            "Você deve aplicar a modificação solicitada no fluxo atual e retornar o JSON COMPLETO E ATUALIZADO do fluxo.\n"
            "Busque manter ao máximo a compatibilidade com os IDs e nós anteriores que não foram alterados.\n\n"
            "🚨 DIRETRIZ DE DETALHAMENTO (NÃO SIMPLIFICAR / COMPREENSIVIDADE):\n"
            "- Não simplifique, resuma ou omita etapas da descrição ou instrução de alteração. Mantenha todos os nós detalhados do fluxo. Cada ação, mensagem, decisão, checagem, validação, chamada de API e script deve virar um nó no fluxo JSON.\n"
            "- Se o usuário citar IDs específicos (ex: ID: 13, ID: 49), mapeie exatamente esse valor no campo \"id\" do nó correspondente para manter rastreabilidade.\n"
            "- Modele todas as ramificações de sucesso e caminhos alternativos/tratamentos de erro detalhadamente.\n\n"
            "REGRAS DE ESTRUTURA DO JSON:\n"
            "1. Nós (Nós de Atividade/Evento/Decisão):\n"
            "   - \"id\": ID do nó (deve manter o ID original caso o nó já existisse).\n"
            "   - \"parent\": ID do nó imediatamente anterior no fluxo principal. O nó de início (Start Event) deve ter parent = null.\n"
            "   - \"edge\": 0 (indica que é um nó).\n"
            "   - \"cod_componente\": 1 para Início/Fim do fluxo (Eventos), 15 para Gateways de decisão/bifurcações, 9 para requisições de API/HTTP, 19 para scripts de processamento local, 17 para caixas de mensagens ou ações comuns (Tasks).\n"
            "   - \"name\": Nome resumido do nó (deve seguir as Regras Gramaticais de nomeação abaixo).\n"
            "   - \"lane\": Nome do papel, setor ou ator responsável (ex: 'Cliente', 'Suporte Técnico', 'Sistema'). Se usar raias, classifique TODOS os nós do fluxo nas raias correspondentes.\n"
            "   - \"task_type\" (obrigatório apenas para cod_componente: 17): Classificação técnica da tarefa. Valores aceitos: user (ação humana), service (chamada de API/serviço), manual (atividade fora do sistema), script (cálculo/script local), send (envio de mensagem ativa), receive (espera de entrada/mensagem).\n"
            "   - \"event_type\" (obrigatório apenas para eventos, cod_componente: 1 ou 11): Classificação técnica do evento. Valores aceitos: timer (tempo/timeout), error (fluxo de erro), terminate (fim total do processo), message (recebimento de mensagem externa).\n\n"
            "2. Conexões/Setas (Edges):\n"
            "   - \"id\": ID string único (ex: 'edge_1').\n"
            "   - \"edge\": 1 (indica que é uma conexão).\n"
            "   - \"source\": ID do nó de origem da conexão.\n"
            "   - \"target\": ID do nó de destino da conexão.\n"
            "   - \"value\": Condição ou rótulo do caminho (ex: 'Sim', 'Não', 'Opção 1', 'Sucesso'). Deve ser vazio para fluxos diretos.\n\n"
            "🚨 REGRAS DE RAMIFICAÇÃO (GATEWAYS):\n"
            "- Para criar bifurcações/decisões, utilize um nó de Gateway ('cod_componente': 15).\n"
            "- O gateway deve ter múltiplas conexões de saída (edges onde 'source' é o ID do gateway, apontando para diferentes nós 'target'). Cada uma dessas conexões deve possuir seu respectivo 'value' descrevendo o caminho da ramificação (ex: 'Sim' na conexão para o nó A, e 'Não' na conexão para o nó B).\n"
            "- Para fundir caminhos alternativos que se reúnem (convergência/merge), crie conexões (edges) dos últimos nós de cada caminho de volta para o mesmo nó de destino comum.\n\n"
            "🚨 REGRAS GRAMATICAIS E SEMÂNTICAS DE NOMEAÇÃO:\n"
            "1. **Para Tarefas/Ações** (cod_componente: 17, 9, 19): o campo 'name' deve OBRIGATORIAMENTE começar com um verbo no infinitivo (ex: 'Enviar mensagem', 'Verificar histórico', 'Solicitar dados').\n"
            "2. **Para Eventos** (início, fim ou intermediários, cod_componente: 1 ou 11): o campo 'name' deve OBRIGATORIAMENTE começar com um verbo no particípio (ex: 'Iniciado atendimento', 'Finalizado com sucesso', 'Aguardado timeout').\n\n"
            "Exemplo de JSON estruturado e ramificado esperado:\n"
            "{\n"
            "  \"flow\": [\n"
            "    { \"id\": 1, \"parent\": null, \"edge\": 0, \"cod_componente\": 1, \"lane\": \"Cliente\", \"name\": \"Iniciado atendimento\" },\n"
            "    { \"id\": 2, \"parent\": 1, \"edge\": 0, \"cod_componente\": 17, \"task_type\": \"user\", \"lane\": \"Cliente\", \"name\": \"Fornecer CPF\" },\n"
            "    { \"id\": 3, \"parent\": 2, \"edge\": 0, \"cod_componente\": 17, \"task_type\": \"service\", \"lane\": \"Sistema\", \"name\": \"Validar cadastro\" },\n"
            "    { \"id\": 4, \"parent\": 3, \"edge\": 0, \"cod_componente\": 15, \"lane\": \"Sistema\", \"name\": \"Verificar resultado da validação\" },\n"
            "    { \"id\": 5, \"parent\": 4, \"edge\": 0, \"cod_componente\": 17, \"task_type\": \"send\", \"lane\": \"Sistema\", \"name\": \"Apresentar menu principal\" },\n"
            "    { \"id\": 6, \"parent\": 4, \"edge\": 0, \"cod_componente\": 1, \"event_type\": \"error\", \"lane\": \"Sistema\", \"name\": \"Finalizado com erro\" },\n"
            "    { \"id\": \"edge_1\", \"edge\": 1, \"source\": 4, \"target\": 5, \"value\": \"Sucesso\" },\n"
            "    { \"id\": \"edge_2\", \"edge\": 1, \"source\": 4, \"target\": 6, \"value\": \"Falha\" }\n"
            "  ]\n"
            "}\n\n"
            "Gere apenas o JSON puro, sem blocos de código markdown ou texto explicativo extra."
        )
        
        prompt = (
            f"{system_instruction}\n\n"
            f"JSON do fluxo atual:\n{json.dumps(flow_data, indent=2, ensure_ascii=False)}\n\n"
            f"Instrução de modificação do usuário: {instruction}"
        )
        
        response_text = generate_llm_response(
            prompt=prompt,
            provider=provider,
            model_name=model_name,
            response_json=True
        )
        
        if not response_text or not response_text.strip():
            raise RuntimeError("Não foi possível obter resposta da IA para refinamento (a resposta está vazia).")
            
        try:
            cleaned_json = extract_json(response_text)
            flow_json = json.loads(cleaned_json)
        except json.JSONDecodeError as jde:
            print("--- ERRO DE DECODE NO REFINE_FLOW ---")
            print(f"Response Text recebido: {repr(response_text)}")
            print(f"Cleaned JSON tentado: {repr(cleaned_json)}")
            print("-------------------------------------")
            raise RuntimeError(
                f"A resposta gerada pela IA para refinamento não pôde ser parseada como JSON estruturado válido.\n"
                f"Detalhes: {jde}\n"
                f"Resposta bruta da IA: {response_text}"
            ) from jde
        
        if 'flow' not in flow_json or not isinstance(flow_json['flow'], list):
            raise ValueError("O formato de fluxo retornado pela IA é inválido.")
            
        # Validar Schema JSON resultante
        try:
            validate(instance=flow_json['flow'], schema=FLOW_SCHEMA)
        except ValidationError as ve:
            return jsonify({"error": f"Schema do fluxo refinado gerado pela IA é inválido: {ve.message}"}), 400

        # Traduzir para BPMN 2.0 XML
        xml_output = generate_bpmn_xml(flow_json['flow'], auto_layout=True)
        
        return jsonify({
            "flow": flow_json['flow'],
            "bpmn_xml": xml_output
        }), 200
        
    except Exception as e:
        traceback.print_exc()
        err_msg = str(e)
        if "429" in err_msg or "quota" in err_msg.lower() or "ResourceExhausted" in err_msg:
            import re
            retry_match = re.search(r"Please retry in ([\d\.]+)s", err_msg)
            retry_after = float(retry_match.group(1)) if retry_match else 10.0
            quota_type = "day" if "PerDay" in err_msg or "day" in err_msg.lower() else "minute"
            return jsonify({
                "error": "Você atingiu o limite de requisições. Por favor, aguarde ou use um modelo local.",
                "retry_after": retry_after,
                "quota_type": quota_type,
                "model": model_name
            }), 429
        return jsonify({"error": f"Erro no refinamento do fluxo: {str(e)}"}), 500

@app.route('/check-models', methods=['GET'])
def check_models():
    """
    Testa a disponibilidade dos modelos de nuvem de forma leve, verificando a existência
    das respectivas chaves de API no arquivo .env (evitando chamadas reais que consomem cota).
    """
    load_dotenv(override=True)
    results = {}
    
    # 1. Verificar Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        results['gemini-3.5-flash'] = {"available": True}
    else:
        results['gemini-3.5-flash'] = {"available": False, "error": "Chave de API do Gemini ausente."}
        
    # 2. Verificar Groq
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        results['groq:llama-3.3-70b-versatile'] = {"available": True}
    else:
        results['groq:llama-3.3-70b-versatile'] = {"available": False, "error": "Chave de API da Groq ausente."}
        
    return jsonify(results), 200

if __name__ == '__main__':
    # Habilitado host='0.0.0.0' para permitir conexões de outros computadores na rede local
    app.run(debug=True, host='0.0.0.0', port=5000)
