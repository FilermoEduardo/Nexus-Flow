import html

def compute_auto_layout(flow_data):
    """
    Algoritmo BFS para calcular coordenadas estruturadas e organizadas do BPMN
    de forma a evitar sobreposições e emaranhados.
    """
    nodes = []
    edges = []
    
    for item in flow_data:
        if item.get('edge') == 1 or 'source' in item:
            edges.append(item)
        else:
            nodes.append(item)
            
    adj = {}
    incoming = {}
    for node in nodes:
        node_id = f"node_{node.get('id', '')}"
        adj[node_id] = []
        incoming[node_id] = 0

    for node in nodes:
        node_id = f"node_{node.get('id', '')}"
        parent_id = f"node_{node.get('parent', '')}"
        if parent_id and parent_id in adj:
            adj[parent_id].append(node_id)
            incoming[node_id] += 1
            
    # Incluir arestas explícitas
    for edge in edges:
        s = f"node_{edge.get('source', '')}"
        t = f"node_{edge.get('target', '')}"
        if s in adj and t in adj:
            if t not in adj[s]:
                adj[s].append(t)
                incoming[t] += 1

    visited = set()
    node_positions = {}
    
    # Encontrar pontos de partida
    roots = [n_id for n_id in adj if incoming.get(n_id, 0) == 0]
    if not roots and adj:
        roots = [list(adj.keys())[0]]

    # BFS para organizar em colunas
    queue = []
    for r in roots:
        queue.append((r, 0))
        visited.add(r)
        
    columns = {}
    
    while queue:
        curr, col = queue.pop(0)
        if col not in columns:
            columns[col] = []
        if curr not in columns[col]:
            columns[col].append(curr)
            
        for child in adj.get(curr, []):
            if child not in visited:
                visited.add(child)
                queue.append((child, col + 1))
                
    # Varredura para nós desconexos
    for n_id in adj:
        if n_id not in visited:
            unvisited_queue = [(n_id, 0)]
            visited.add(n_id)
            while unvisited_queue:
                curr, col = unvisited_queue.pop(0)
                if col not in columns:
                    columns[col] = []
                if curr not in columns[col]:
                    columns[col].append(curr)
                for child in adj.get(curr, []):
                    if child not in visited:
                        visited.add(child)
                        unvisited_queue.append((child, col + 1))

    # Dimensões da grade
    col_width = 300
    row_height = 180
    
    # Encontrar a altura máxima de coluna para calcular um centro Y seguro e dinâmico
    max_rows = max(len(node_ids) for node_ids in columns.values()) if columns else 1
    mid_y = (max_rows * row_height) / 2 + 100
    
    for col, node_ids in columns.items():
        n_rows = len(node_ids)
        # Ponto inicial Y para que esta coluna fique centralizada verticalmente em relação a mid_y
        start_y = mid_y - ((n_rows - 1) * row_height) / 2
        
        for row, n_id in enumerate(node_ids):
            grid_x = 100 + col * col_width
            grid_y = start_y + row * row_height
            node_positions[n_id] = (grid_x, grid_y)
            
    return node_positions


def generate_bpmn_xml(flow_data, auto_layout=False):
    """
    Gera o XML BPMN 2.0.
    Se auto_layout for True, as coordenadas são calculadas programaticamente.
    Se False, usa as coordenadas brutas do JSON multiplicadas pelo SPACING.
    """
    children_map = {}
    for node in flow_data:
        node_id = f"node_{node.get('id', '')}"
        if node_id not in children_map:
            children_map[node_id] = []
        
        parent = node.get('parent')
        if parent:
            parent_id = f"node_{parent}"
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(node_id)

    xml_process = []
    xml_diagram = []
    
    SPACING = 2.0
    layout_positions = {}
    if auto_layout:
        layout_positions = compute_auto_layout(flow_data)

    # Dicionário para guardar coordenadas finais de cada nó para desenhar as arestas depois
    coords = {}

    for node in flow_data:
        # Desconsiderar arestas/edges no desenho inicial de nós
        if node.get('edge') == 1 or 'source' in node:
            continue

        raw_id = node.get('id', '')
        node_id = f"node_{raw_id}"
        
        raw_parent = node.get('parent')
        cod_componente = node.get('cod_componente', '')
        
        raw_name = str(node.get('name', f"Node {raw_id}"))
        name = html.escape(raw_name).replace('"', '&quot;')
        
        has_parent = bool(raw_parent)
        has_children = len(children_map.get(node_id, [])) > 0

        # 1. Definir dimensões com base na forma
        if not has_parent:
            # StartEvent (Círculo)
            width, height = 36, 36
        elif not has_children:
            # EndEvent (Círculo)
            width, height = 36, 36
        else:
            if "gateway" in str(cod_componente).lower() or str(cod_componente) == "exclusiveGateway" or cod_componente == 15:
                # Gateway (Losango)
                width, height = 50, 50
            else:
                # Task (Retângulo)
                width, height = 100, 80

        # 2. Definir posicionamento x, y
        if auto_layout and node_id in layout_positions:
            grid_x, grid_y = layout_positions[node_id]
            x = grid_x - (width / 2)
            y = grid_y - (height / 2)
        else:
            x = float(node.get('x', 0)) * SPACING
            y = float(node.get('y', 0)) * SPACING

        # Guardar coordenadas para as conexões
        coords[node_id] = (x, y, width, height)

        # 3. Gerar tags do elemento
        if not has_parent:
            bpmn_element = f'<bpmn:startEvent id="{node_id}" name="{name}"></bpmn:startEvent>'
            xml_diagram.append(f'''
            <bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}">
                <dc:Bounds x="{x}" y="{y}" width="{width}" height="{height}" />
            </bpmndi:BPMNShape>
            ''')
        elif not has_children:
            bpmn_element = f'<bpmn:endEvent id="{node_id}" name="{name}"></bpmn:endEvent>'
            xml_diagram.append(f'''
            <bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}">
                <dc:Bounds x="{x}" y="{y}" width="{width}" height="{height}" />
            </bpmndi:BPMNShape>
            ''')
        else:
            if "gateway" in str(cod_componente).lower() or str(cod_componente) == "exclusiveGateway" or cod_componente == 15:
                bpmn_element = f'<bpmn:exclusiveGateway id="{node_id}" name="{name}"></bpmn:exclusiveGateway>'
                xml_diagram.append(f'''
            <bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}" isMarkerVisible="true">
                <dc:Bounds x="{x}" y="{y}" width="{width}" height="{height}" />
            </bpmndi:BPMNShape>
            ''')
            else:
                bpmn_element = f'<bpmn:task id="{node_id}" name="{name}"></bpmn:task>'
                xml_diagram.append(f'''
            <bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}">
                <dc:Bounds x="{x}" y="{y}" width="{width}" height="{height}" />
            </bpmndi:BPMNShape>
            ''')

        xml_process.append(bpmn_element)

    # 4. Gerar setas (SequenceFlow)
    for node in flow_data:
        # Apenas nós (ignora as setas físicas do JSON para recriar as conexões de forma alinhada)
        if node.get('edge') == 1 or 'source' in node:
            continue

        raw_id = node.get('id', '')
        node_id = f"node_{raw_id}"
        
        raw_parent = node.get('parent')
        has_parent = bool(raw_parent)

        if has_parent:
            parent_id = f"node_{raw_parent}"
            flow_id = f"Flow_{parent_id}_{node_id}"
            
            xml_process.append(f'<bpmn:sequenceFlow id="{flow_id}" sourceRef="{parent_id}" targetRef="{node_id}" />')
            
            # Obter coordenadas para alinhar as setas
            px, py, pw, ph = coords.get(parent_id, (0, 0, 100, 80))
            cx, cy, cw, ch = coords.get(node_id, (0, 0, 100, 80))
            
            # Centro das figuras
            p_center_x = px + (pw / 2)
            p_center_y = py + (ph / 2)
            c_center_x = cx + (cw / 2)
            c_center_y = cy + (ch / 2)

            xml_diagram.append(f'''
            <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">
                <di:waypoint x="{p_center_x}" y="{p_center_y}" />
                <di:waypoint x="{c_center_x}" y="{c_center_y}" />
            </bpmndi:BPMNEdge>
            ''')

    process_xml = "\n    ".join(xml_process)
    diagram_xml = "\n    ".join(xml_diagram)

    full_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" 
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" 
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" 
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI" 
                  id="Definitions_1" 
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_1" isExecutable="true">
    {process_xml}
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      {diagram_xml}
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>'''
    
    return full_xml.strip()