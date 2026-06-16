# pyrefly: ignore [missing-import]
import os
import json
import base64
import requests
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import google.generativeai as genai
from translator import generate_bpmn_xml
from drawio_parser import parse_drawio_to_json

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv(override=True)

# Configura o Gemini
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

app = Flask(__name__)
CORS(app)

def generate_llm_response(prompt, provider, model_name, attached_file=None, response_json=False):
    """
    Função unificada para gerar conteúdo usando Gemini (nuvem) ou Ollama (local).
    """
    if provider == "ollama":
        # Chamada ao Ollama Local
        url = "http://localhost:11434/api/generate"
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False
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
            
        # Faz a requisição POST para o Ollama local
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
        import time
        for attempt in range(3):
            try:
                res = model.generate_content(contents, generation_config=generation_config)
                return res.text
            except Exception as ex:
                if attempt == 2:
                    raise ex
                time.sleep(2 ** attempt)

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        data = request.get_json(force=True)
        if not data or 'flow' not in data or not isinstance(data['flow'], list):
            raise ValueError("Invalid flow structure")
            
        auto_layout = request.args.get('auto_layout', 'false').lower() == 'true' or data.get('auto_layout', False)
        flow_data = data['flow']
        xml_output = generate_bpmn_xml(flow_data, auto_layout=auto_layout)
        
        return xml_output, 200, {'Content-Type': 'application/xml'}
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro Interno: {str(e)}"}), 400

@app.route('/convert-drawio', methods=['POST'])
def convert_drawio():
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "Nenhum arquivo enviado."}), 400
            
        content = file.read().decode('utf-8', errors='ignore')
        result_json = parse_drawio_to_json(content)
        
        return jsonify(result_json), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Erro na conversão: {str(e)}"}), 500

@app.route('/chat', methods=['POST'])
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

        # Obtém o motor de IA do header (ex: "gemini:gemini-2.5-flash" ou "ollama:qwen2.5:3b")
        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-2.5-flash')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-2.5-flash'

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
            return jsonify({
                "error": "Você atingiu o limite de requisições do Oraculo (2 requisições por minuto). Por favor, aguarde cerca de 1 minuto antes de tentar novamente ou use um modelo local."
            }), 429
            
        return jsonify({"error": f"Erro no Oráculo: {err_msg}"}), 500

@app.route('/generate-multimodal', methods=['POST'])
def generate_multimodal():
    try:
        # Pega a descrição de texto se houver
        question = request.form.get('description', '')
        
        # Pega o arquivo de mídia se houver
        attached_file = request.files.get('file')
        
        if not question and not attached_file:
            return jsonify({"error": "Forneça uma descrição em texto ou envie um arquivo de áudio/imagem/PDF."}), 400

        # Obtém o motor de IA do header (ex: "gemini:gemini-2.5-flash" ou "ollama:qwen2.5:3b")
        ai_engine = request.headers.get('X-Provider-Model', 'gemini:gemini-2.5-flash')
        parts = ai_engine.split(':')
        provider = parts[0] if len(parts) > 0 else 'gemini'
        model_name = ':'.join(parts[1:]) if len(parts) > 1 else 'gemini-2.5-flash'
            
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
            
        # Converte o fluxo gerado pela IA em XML BPMN 2.0 com auto_layout ativado
        xml_output = generate_bpmn_xml(flow_json['flow'], auto_layout=True)
        
        return xml_output, 200, {
            'Content-Type': 'application/xml',
            'Content-Disposition': 'attachment; filename=fluxo_gerado.bpmn'
        }
        
    except Exception as e:
        traceback.print_exc()
        err_msg = str(e)
        if "429" in err_msg or "quota" in err_msg.lower() or "ResourceExhausted" in err_msg:
            return jsonify({
                "error": "Você atingiu a cota limite de requisições gratuitas do Gemini. Por favor, aguarde alguns segundos ou use um modelo local."
            }), 429
        return jsonify({"error": f"Erro na geração inteligente: {str(e)}"}), 500

if __name__ == '__main__':
    # Habilitado host='0.0.0.0' para permitir conexões de outros computadores na rede local
    app.run(debug=True, host='0.0.0.0', port=5000)
