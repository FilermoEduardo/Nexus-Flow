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
# pyrefly: ignore [missing-import]
import google.generativeai as genai
from translator import generate_bpmn_xml
from drawio_parser import parse_drawio_to_json
from jsonschema import validate, ValidationError
# pyrefly: ignore [missing-import]
from flask_limiter import Limiter
# pyrefly: ignore [missing-import]
from flask_limiter.util import get_remote_address

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv(override=True)

# Configura o Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

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
            "value": {"type": "string"}
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

def generate_llm_response(prompt, provider, model_name, attached_file=None, response_json=False, stream=False):
    """
    Função unificada para gerar conteúdo usando Gemini (nuvem) ou Ollama (local),
    com suporte para streaming de respostas (Melhoria 2).
    """
    if provider == "ollama":
        # Chamada ao Ollama Local
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": stream
        }
        if response_json:
            payload["format"] = "json"
            
        if attached_file:
            # Se for um arquivo de imagem, o Ollama suporta envio em base64 no campo 'images'
            content_type = attached_file.content_type or ""
            if "image" in content_type:
                attached_file.seek(0)
                file_bytes = attached_file.read()
                b64_img = base64.b64encode(file_bytes).decode('utf-8')
                payload["images"] = [b64_img]
            
        if stream:
            # Gerador para streaming do Ollama
            def ollama_stream_generator():
                response = requests.post(url, json=payload, timeout=120, stream=True)
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        try:
                            res_data = json.loads(line.decode('utf-8'))
                            token = res_data.get("response", "")
                            if token:
                                yield token
                        except Exception:
                            pass
            return ollama_stream_generator()
        else:
            # Chamada convencional Ollama
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            res_data = response.json()
            return res_data.get("response", "")
    else:
        # Carrega e configura o Gemini dinamicamente a cada requisição
        load_dotenv(override=True)
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

        # Chamada ao Gemini na nuvem (Padrão)
        actual_model = model_name
        # Mapeamento dinâmico para os modelos mais novos
        if "3.5-flash" in model_name:
            actual_model = "gemini-2.5-flash"
        elif "3.5-pro" in model_name:
            actual_model = "gemini-2.5-pro"
            
        model = genai.GenerativeModel(model_name=actual_model)
        
        contents = []
        if attached_file:
            attached_file.seek(0)
            file_bytes = attached_file.read()
            contents.append({
                "mime_type": attached_file.content_type,
                "data": file_bytes
            })
        contents.append(prompt)
        
        generation_config = {}
        if response_json:
            generation_config["response_mime_type"] = "application/json"
            
        # Tentativa de chamada com backoff exponencial contra timeouts temporários (504)
        for attempt in range(3):
            try:
                if stream:
                    res = model.generate_content(contents, generation_config=generation_config, stream=True)
                    # Gerador para streaming do Gemini
                    def gemini_stream_generator():
                        for chunk in res:
                            if chunk.text:
                                yield chunk.text
                    return gemini_stream_generator()
                else:
                    res = model.generate_content(contents, generation_config=generation_config)
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
        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-flash-lite-latest')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-flash-lite-latest'

        # Filtrar propriedades visuais para economizar tokens
        clean_flow = []
        if isinstance(flow_data, list):
            logical_keys = ['id', 'parent', 'edge', 'source', 'target', 'cod_componente', 'value', 'data']
            for node in flow_data:
                cleaned_node = {k: node[k] for k in logical_keys if k in node}
                clean_flow.append(cleaned_node)
        
        system_instruction = (
            "Você é um Especialista em UX Conversacional e Arquiteto de Soluções de Chatbot. "
            "Sua tarefa é analisar o fluxo de dados técnico em JSON de um chatbot legado e auxiliar a equipe de manutenção.\n\n"
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
            f"JSON do fluxo de dados:\n{json.dumps(clean_flow, indent=2, ensure_ascii=False)}\n\n"
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

        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-flash-lite-latest')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-flash-lite-latest'

        clean_flow = []
        if isinstance(flow_data, list):
            logical_keys = ['id', 'parent', 'edge', 'source', 'target', 'cod_componente', 'value', 'data']
            for node in flow_data:
                cleaned_node = {k: node[k] for k in logical_keys if k in node}
                clean_flow.append(cleaned_node)
        
        system_instruction = (
            "Você é um Especialista em UX Conversacional e Arquiteto de Soluções de Chatbot. "
            "Sua tarefa é analisar o fluxo de dados técnico em JSON de um chatbot legado e auxiliar a equipe de manutenção.\n\n"
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
            f"JSON do fluxo de dados:\n{json.dumps(clean_flow, indent=2, ensure_ascii=False)}\n\n"
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
        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-flash-lite-latest')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-flash-lite-latest'
            
        system_instruction = (
            "Você é um arquiteto especialista em Chatbots e engenharia de processos BPMN 2.0. "
            "Sua tarefa é analisar a descrição enviada (seja em áudio, imagem, PDF ou texto) e convertê-la estruturalmente em um fluxo de atendimento para chatbot. "
            "Você deve retornar a resposta estritamente em formato JSON no esquema detalhado abaixo. "
            "Esquema JSON esperado:\n"
            "{\n"
            "  \"flow\": [\n"
            "    {\n"
            "      \"id\": 1, // ID inteiro incremental único para o nó\n"
            "      \"parent\": null, // ID do nó anterior. O nó inicial de saudação deve ter parent = null\n"
            "      \"edge\": 0, // Identifica que é um nó\n"
            "      \"cod_componente\": 17, // 1 para Início/Fim do fluxo, 15 para Gateways de decisão/bifurcações, 9 para requisições de API/HTTP, 17 para caixas de mensagens comuns\n"
            "      \"name\": \"Texto curto resumindo a ação do bloco\" // Ex: 'Saudação', 'Escolha de Menu', 'Consultar CPF', 'Resposta Suporte'\n"
            "    },\n"
            "    {\n"
            "      \"id\": \"edge_1\", // ID da conexão\n"
            "      \"edge\": 1, // Identifica que é uma conexão/seta\n"
            "      \"source\": 1, // ID do nó de origem\n"
            "      \"target\": 2, // ID do nó de destino\n"
            "      \"value\": \"Opção Escolhida\" // Condição ou label da conexão (ex: 'Sim', 'Não', 'Opção 1', 'Sucesso'). Vazio se for fluxo direto.\n"
            "    }\n"
            "  ]\n"
            "}\n"
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
            
        if not response_text:
            raise RuntimeError("Não foi possível obter uma resposta válida do provedor de IA.")
            
        # Parseia o JSON retornado
        flow_json = json.loads(response_text.strip())
        
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
            
        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-flash-lite-latest')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-flash-lite-latest'
        
        system_instruction = (
            "Você é um arquiteto especialista em Chatbots e engenharia de processos BPMN 2.0.\n"
            "Sua tarefa é receber o JSON de um fluxo de chatbot existente e uma instrução de refinamento/modificação do usuário.\n"
            "Você deve aplicar a modificação solicitada no fluxo atual e retornar o JSON COMPLETO E ATUALIZADO do fluxo.\n"
            "Busque manter ao máximo a compatibilidade com os IDs e nós anteriores que não foram alterados.\n"
            "Esquema JSON esperado:\n"
            "{\n"
            "  \"flow\": [\n"
            "    {\n"
            "      \"id\": 1, // ID do nó\n"
            "      \"parent\": null,\n"
            "      \"edge\": 0,\n"
            "      \"cod_componente\": 17,\n"
            "      \"name\": \"Saudação\"\n"
            "    },\n"
            "    {\n"
            "      \"id\": \"edge_1\",\n"
            "      \"edge\": 1,\n"
            "      \"source\": 1,\n"
            "      \"target\": 2,\n"
            "      \"value\": \"Opção Escolhida\"\n"
            "    }\n"
            "  ]\n"
            "}\n"
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
        
        if not response_text:
            raise RuntimeError("Não foi possível obter resposta da IA para refinamento.")
            
        flow_json = json.loads(response_text.strip())
        
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
    Testa em paralelo a disponibilidade e cotas de todos os modelos Gemini configurados.
    Retorna o status estruturado de cada um, incluindo tempo de retry se estiver sob cota.
    """
    from concurrent.futures import ThreadPoolExecutor
    
    models_to_test = [
        'gemini-flash-lite-latest',
        'gemini-3.1-flash-lite',
        'gemini-flash-latest',
        'gemini-2.0-flash-lite',
        'gemini-3.5-flash',
        'gemini-3.5-pro'
    ]
    
    load_dotenv(override=True)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({m: {"available": False, "error": "Chave de API ausente."} for m in models_to_test}), 200
        
    genai.configure(api_key=api_key)
    results = {}
    
    def test_model(model_name):
        try:
            model = genai.GenerativeModel(model_name)
            # Requisição mínima para testar resposta gRPC rapidamente
            res = model.generate_content('Oi', generation_config={"max_output_tokens": 1})
            return model_name, {"available": True}
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "quota" in err_msg.lower() or "ResourceExhausted" in err_msg:
                import re
                retry_match = re.search(r"Please retry in ([\d\.]+)s", err_msg)
                retry_after = float(retry_match.group(1)) if retry_match else 10.0
                quota_type = "day" if "PerDay" in err_msg or "day" in err_msg.lower() else "minute"
                return model_name, {
                    "available": False,
                    "retry_after": retry_after,
                    "quota_type": quota_type,
                    "error": "Cota excedida"
                }
            elif "404" in err_msg or "not found" in err_msg.lower():
                return model_name, {
                    "available": False,
                    "error": "Modelo não suportado ou não encontrado."
                }
            return model_name, {
                "available": False,
                "error": err_msg[:100]
            }

    with ThreadPoolExecutor(max_workers=len(models_to_test)) as executor:
        futures = [executor.submit(test_model, m) for m in models_to_test]
        for future in futures:
            try:
                m_name, m_res = future.result(timeout=10)
                results[m_name] = m_res
            except Exception:
                pass
                
    return jsonify(results), 200

if __name__ == '__main__':
    # Habilitado host='0.0.0.0' para permitir conexões de outros computadores na rede local
    app.run(debug=True, host='0.0.0.0', port=5000)
