import base64
import zlib
import urllib.parse
import xml.etree.ElementTree as ET

def decode_drawio_diagram(xml_string):
    """
    Decodifica e descompacta arquivos .drawio salvos no formato padrão (comprimido).
    Caso o XML já esteja descompactado, retorna a string original.
    """
    try:
        root = ET.fromstring(xml_string.strip())
        
        # O Draw.io comprimido coloca o conteúdo em tags <diagram> em formato Base64 + Deflate
        diagram_nodes = root.findall('.//diagram')
        if not diagram_nodes:
            # Se for apenas <mxGraphModel> direto, já está descompactado
            if root.tag == 'mxGraphModel' or root.find('.//mxGraphModel') is not None:
                return xml_string
            return xml_string
            
        diagram_node = diagram_nodes[0]
        diagram_data = diagram_node.text
        
        if not diagram_data:
            # Às vezes o mxGraphModel está dentro da tag diagram sem compressão
            mx_model = diagram_node.find('.//mxGraphModel')
            if mx_model is not None:
                return ET.tostring(mx_model, encoding='utf-8').decode('utf-8')
            return xml_string

        # Decodifica Base64
        decoded = base64.b64decode(diagram_data.strip())
        # Descomprime (deflate com wbits=-15 para ignorar cabeçalhos zlib)
        decompressed = zlib.decompress(decoded, -15)
        # Decodifica URL
        xml_unquoted = urllib.parse.unquote(decompressed.decode('utf-8'))
        return xml_unquoted
    except Exception as e:
        print(f"[drawio_parser] Erro ao descompactar diagrama: {e}")
        # Em caso de erro, tenta retornar o XML original
        return xml_string

def parse_drawio_to_json(xml_content):
    """
    Analisa um arquivo XML/mxGraphModel do Draw.io e o converte para o formato JSON da Estella.
    """
    # 1. Descompacta se necessário
    decompressed_xml = decode_drawio_diagram(xml_content)
    
    try:
        root = ET.fromstring(decompressed_xml.strip())
    except Exception as e:
        raise ValueError(f"XML inválido ou corrompido: {e}")

    # Lista final de elementos do fluxo
    flow = []
    
    # Dicionários temporários para ajudar no mapeamento lógico
    vertices = {}
    edges = []
    
    # Mapeia conexões de entrada: target_node_id -> source_node_id
    # Usado para inferir a lógica de "parent" nos nós
    incoming_connections = {}

    # Encontrar todas as células mxCell
    mx_cells = root.findall('.//mxCell')
    
    # Primeira varredura: Coletar os vértices (nós) e arestas (setas)
    for cell in mx_cells:
        cell_id = cell.get('id')
        if not cell_id or cell_id in ('0', '1'):
            # Células de controle padrão do Draw.io (id 0 e 1 são o root e parent principal)
            continue
            
        is_vertex = cell.get('vertex') == '1'
        is_edge = cell.get('edge') == '1'
        
        # Pega o container/parent do mxCell no XML (visual)
        visual_parent = cell.get('parent', '1')
        if visual_parent in ('0', '1'):
            visual_parent = 1
        else:
            try:
                visual_parent = int(visual_parent)
            except ValueError:
                pass

        if is_vertex:
            # É uma caixa de fluxo (nó)
            value = cell.get('value', '')
            style = cell.get('style', '')
            
            # Extrair coordenadas e dimensões
            geometry = cell.find('mxGeometry')
            x = 0
            y = 0
            width = 100
            height = 80
            
            if geometry is not None:
                x = float(geometry.get('x', 0))
                y = float(geometry.get('y', 0))
                width = float(geometry.get('width', 100))
                height = float(geometry.get('height', 80))

            # Mapeamento do de-para do cod_componente
            style_lower = style.lower()
            if 'rhombus' in style_lower:
                cod_componente = 15  # Gateway/Decisão
            elif 'ellipse' in style_lower:
                cod_componente = 1   # Início/Fim (Start/End)
            elif 'rounded' in style_lower or 'rectangle' in style_lower or not style:
                cod_componente = 17  # Mensagem (Padrão)
            else:
                cod_componente = 8   # Outros componentes / Decisões genéricas
                
            vertices[cell_id] = {
                "id": int(cell_id) if cell_id.isdigit() else cell_id,
                "parent": visual_parent, # Default visual, será sobrescrito pelo parentesco lógico
                "edge": 0,
                "cod_componente": cod_componente,
                "height": int(height),
                "width": int(width),
                "x": int(x),
                "y": int(y),
                "relative": 0,
                "value": value,
                "data": {
                    "identifier": f"node_{cell_id}"
                }
            }
            
        elif is_edge:
            # É uma seta de fluxo (aresta)
            source = cell.get('source')
            target = cell.get('target')
            value = cell.get('value', '')
            
            if source and target:
                edges.append({
                    "id": int(cell_id) if cell_id.isdigit() else cell_id,
                    "parent": visual_parent,
                    "edge": 1,
                    "cod_componente": "",
                    "source": int(source) if source.isdigit() else source,
                    "target": int(target) if target.isdigit() else target,
                    "value": value,
                    "style": cell.get('style', ''),
                    "data": {
                        "condition": value
                    }
                })
                
                # Guarda a conexão para definir o predecessor (parent lógico)
                if target not in incoming_connections:
                    incoming_connections[target] = source

    # Segunda etapa: Aplicar o parentesco lógico baseado nas conexões (edges)
    # Regra: O parent do nó B é o source da seta onde target=B
    for node_id, node_data in vertices.items():
        if node_id in incoming_connections:
            source_id = incoming_connections[node_id]
            node_data["parent"] = int(source_id) if source_id.isdigit() else source_id
        else:
            # Sem pai lógico significa que é um ponto de entrada (StartEvent)
            # Fica associado ao container principal (geralmente 1)
            node_data["parent"] = 1

    # Une os nós e as arestas na lista final de fluxo
    flow.extend(vertices.values())
    flow.extend(edges)
    
    return {"flow": flow}
