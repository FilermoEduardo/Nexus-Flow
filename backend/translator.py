import html
import re
import unicodedata

def simplify_lane_name(name):
    """
    Normaliza e simplifica o nome da lane para ser usado como ID válido.
    """
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8')
    s = re.sub(r'[^a-zA-Z0-9_]', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s

def compute_auto_layout(flow_data):
    """
    Algoritmo BFS para calcular coordenadas estruturadas e organizadas do BPMN
    de forma a evitar sobreposições e emaranhados, com suporte para Swimlanes (Lanes).
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

    # Verificar se há lanes
    has_lanes = False
    lanes_set = []
    node_to_lane = {}
    
    for node in nodes:
        lane = node.get('lane')
        if lane:
            has_lanes = True
            if lane not in lanes_set:
                lanes_set.append(lane)
                
    if has_lanes:
        has_any_nolaned_nodes = any(not node.get('lane') for node in nodes)
        if has_any_nolaned_nodes:
            if "Geral" not in lanes_set:
                lanes_set.append("Geral")
        for node in nodes:
            n_id = f"node_{node.get('id')}"
            lane = node.get('lane')
            if not lane:
                node_to_lane[n_id] = "Geral"
            else:
                node_to_lane[n_id] = lane

    # Dimensões da grade
    col_width = 380  # Aumentado para dar mais espaço horizontal para setas e labels
    row_height = 200
    
    lane_heights = {}
    if has_lanes:
        for lane in lanes_set:
            max_k = 0
            for col, node_ids in columns.items():
                lane_nodes = [nid for nid in node_ids if node_to_lane.get(nid) == lane]
                max_k = max(max_k, len(lane_nodes))
            # Garante pelo menos 130px de espaço vertical para cada nó na coluna mais densa
            lane_heights[lane] = max(250, max_k * 130 + 50)

        lane_offsets = {}
        current_offset = 50
        for lane in lanes_set:
            lane_offsets[lane] = current_offset
            current_offset += lane_heights[lane]

        for col, node_ids in columns.items():
            for lane in lanes_set:
                lane_nodes = [nid for nid in node_ids if node_to_lane.get(nid) == lane]
                k = len(lane_nodes)
                if k == 0:
                    continue
                
                y_start = lane_offsets[lane]
                l_height = lane_heights[lane]
                lane_center_y = y_start + (l_height / 2)
                
                if k == 1:
                    grid_x = 100 + col * col_width
                    grid_y = lane_center_y
                    node_positions[lane_nodes[0]] = (grid_x, grid_y)
                else:
                    margin = 50
                    usable_height = l_height - 2 * margin
                    for idx, nid in enumerate(lane_nodes):
                        grid_x = 100 + col * col_width
                        grid_y = y_start + margin + idx * (usable_height / (k - 1))
                        node_positions[nid] = (grid_x, grid_y)
    else:
        # Encontrar a altura máxima de coluna para calcular um centro Y seguro e dinâmico (sem lanes)
        max_rows = max(len(node_ids) for node_ids in columns.values()) if columns else 1
        mid_y = (max_rows * row_height) / 2 + 100
        
        for col, node_ids in columns.items():
            n_rows = len(node_ids)
            start_y = mid_y - ((n_rows - 1) * row_height) / 2
            
            for row, n_id in enumerate(node_ids):
                grid_x = 100 + col * col_width
                grid_y = start_y + row * row_height
                node_positions[n_id] = (grid_x, grid_y)
                
    return node_positions, lane_heights


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

    # Identificar nós e verificar se há lanes
    nodes = [node for node in flow_data if not (node.get('edge') == 1 or 'source' in node)]
    has_lanes = False
    lanes_set = []
    node_to_lane = {}
    for node in nodes:
        lane = node.get('lane')
        if lane:
            has_lanes = True
            if lane not in lanes_set:
                lanes_set.append(lane)
    
    if has_lanes:
        has_any_nolaned_nodes = any(not node.get('lane') for node in nodes)
        if has_any_nolaned_nodes:
            if "Geral" not in lanes_set:
                lanes_set.append("Geral")
        for node in nodes:
            n_id = f"node_{node.get('id')}"
            lane = node.get('lane')
            if not lane:
                node_to_lane[n_id] = "Geral"
            else:
                node_to_lane[n_id] = lane

    xml_process = []
    xml_diagram = []
    
    SPACING = 2.0
    layout_positions = {}
    lane_heights = {}
    if auto_layout:
        layout_positions, lane_heights = compute_auto_layout(flow_data)

    # Dicionário para guardar coordenadas finais de cada nó para desenhar as arestas depois
    coords = {}

    for node in nodes:
        raw_id = node.get('id', '')
        node_id = f"node_{raw_id}"
        
        raw_parent = node.get('parent')
        cod_componente = node.get('cod_componente', '')
        
        raw_name = str(node.get('name', f"Node {raw_id}"))
        name = html.escape(raw_name).replace('"', '&quot;')
        
        has_parent = bool(raw_parent)
        has_children = len(children_map.get(node_id, [])) > 0

        is_gateway = "gateway" in str(cod_componente).lower() or str(cod_componente) == "exclusiveGateway" or cod_componente == 15
        is_event = (not has_parent) or (not has_children) or ('event_type' in node) or (cod_componente in [1, 11])

        # 1. Definir dimensões com base na forma
        if is_event:
            width, height = 36, 36
        elif is_gateway:
            width, height = 50, 50
        else:
            width, height = 120, 80  # Aumentado para 120 para melhor contraste e visualização do texto interno

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
        if is_event:
            event_type = node.get('event_type')
            child_tag = ""
            if event_type == "timer":
                child_tag = "<bpmn:timerEventDefinition />"
            elif event_type == "terminate":
                child_tag = "<bpmn:terminateEventDefinition />"
            elif event_type == "error":
                child_tag = "<bpmn:errorEventDefinition />"
            elif event_type == "message":
                child_tag = "<bpmn:messageEventDefinition />"

            if not has_parent:
                tag_name = "bpmn:startEvent"
            elif not has_children:
                tag_name = "bpmn:endEvent"
            else:
                if event_type == "terminate":
                    tag_name = "bpmn:intermediateThrowEvent"
                else:
                    tag_name = "bpmn:intermediateCatchEvent"

            if child_tag:
                bpmn_element = f'<{tag_name} id="{node_id}" name="{name}">{child_tag}</{tag_name}>'
            else:
                bpmn_element = f'<{tag_name} id="{node_id}" name="{name}"></{tag_name}>'

            xml_diagram.append(f'''
        <bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}">
            <dc:Bounds x="{x}" y="{y}" width="{width}" height="{height}" />
        </bpmndi:BPMNShape>
            ''')
        elif is_gateway:
            bpmn_element = f'<bpmn:exclusiveGateway id="{node_id}" name="{name}"></bpmn:exclusiveGateway>'
            xml_diagram.append(f'''
        <bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}" isMarkerVisible="true">
            <dc:Bounds x="{x}" y="{y}" width="{width}" height="{height}" />
        </bpmndi:BPMNShape>
            ''')
        else:
            task_type = node.get('task_type')
            if task_type == "user":
                tag_name = "bpmn:userTask"
            elif task_type == "service":
                tag_name = "bpmn:serviceTask"
            elif task_type == "manual":
                tag_name = "bpmn:manualTask"
            elif task_type == "script":
                tag_name = "bpmn:scriptTask"
            elif task_type == "send":
                tag_name = "bpmn:sendTask"
            elif task_type == "receive":
                tag_name = "bpmn:receiveTask"
            else:
                tag_name = "bpmn:task"

            bpmn_element = f'<{tag_name} id="{node_id}" name="{name}"></{tag_name}>'
            xml_diagram.append(f'''
        <bpmndi:BPMNShape id="{node_id}_di" bpmnElement="{node_id}">
            <dc:Bounds x="{x}" y="{y}" width="{width}" height="{height}" />
        </bpmndi:BPMNShape>
            ''')

        xml_process.append(bpmn_element)

    # 4. Gerar setas (SequenceFlow)
    generated_flows = set()

    for node in flow_data:
        if node.get('edge') == 1 or 'source' in node:
            continue

        raw_id = node.get('id', '')
        node_id = f"node_{raw_id}"
        
        raw_parent = node.get('parent')
        has_parent = bool(raw_parent)

        if has_parent:
            parent_id = f"node_{raw_parent}"
            flow_pair = (parent_id, node_id)
            if flow_pair not in generated_flows:
                generated_flows.add(flow_pair)
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

    # Gerar a partir de conexões explícitas (edge: 1) para permitir convergência/merge de múltiplos fluxos
    for edge in flow_data:
        if edge.get('edge') == 1 or ('source' in edge and 'target' in edge):
            s_val = edge.get('source')
            t_val = edge.get('target')
            if s_val is not None and t_val is not None:
                parent_id = f"node_{s_val}"
                node_id = f"node_{t_val}"
                flow_pair = (parent_id, node_id)
                if flow_pair not in generated_flows and parent_id in coords and node_id in coords:
                    generated_flows.add(flow_pair)
                    flow_id = f"Flow_{parent_id}_{node_id}"
                    
                    flow_name = str(edge.get('value', '') or '').strip()
                    name_attr = f' name="{html.escape(flow_name)}"' if flow_name else ''
                    
                    xml_process.append(f'<bpmn:sequenceFlow id="{flow_id}"{name_attr} sourceRef="{parent_id}" targetRef="{node_id}" />')
                    
                    px, py, pw, ph = coords.get(parent_id)
                    cx, cy, cw, ch = coords.get(node_id)
                    
                    p_center_x = px + (pw / 2)
                    p_center_y = py + (ph / 2)
                    c_center_x = cx + (cw / 2)
                    c_center_y = cy + (ch / 2)

                    # Adiciona label visual no diagrama no ponto médio
                    label_xml = ""
                    if flow_name:
                        lx = (p_center_x + c_center_x) / 2 - 20
                        ly = (p_center_y + c_center_y) / 2 - 10
                        label_xml = f'''
            <bpmndi:BPMNLabel>
                <dc:Bounds x="{lx}" y="{ly}" width="60" height="20" />
            </bpmndi:BPMNLabel>'''

                    xml_diagram.append(f'''
        <bpmndi:BPMNEdge id="{flow_id}_di" bpmnElement="{flow_id}">
            <di:waypoint x="{p_center_x}" y="{p_center_y}" />
            <di:waypoint x="{c_center_x}" y="{c_center_y}" />{label_xml}
        </bpmndi:BPMNEdge>
                    ''')

    collaboration_xml = ""
    lane_shapes_xml = []

    if has_lanes:
        lane_node_refs = {lane: [] for lane in lanes_set}
        for nid, lane in node_to_lane.items():
            lane_node_refs[lane].append(nid)

        # Ordenar as lanes pelo Y médio de seus nós se não for auto_layout
        if not auto_layout:
            lane_avg_y = {}
            for lane in lanes_set:
                nids = lane_node_refs[lane]
                if nids:
                    lane_avg_y[lane] = sum(coords[nid][1] for nid in nids) / len(nids)
                else:
                    lane_avg_y[lane] = 0
            lanes_set = sorted(lanes_set, key=lambda l: lane_avg_y.get(l, 0))

        lane_height = 250
        pool_y = 50

        all_xs = [coords[nid][0] for nid in coords]
        all_widths = [coords[nid][2] for nid in coords]

        min_x_geral = min(all_xs) if all_xs else 100
        max_x_geral = max(all_xs[i] + all_widths[i] for i in range(len(all_xs))) if all_xs else 1000

        pool_x = max(min_x_geral - 100, 50)
        pool_width = (max_x_geral - pool_x) + 200

        y_curr = pool_y
        lane_y_positions = {}
        lane_height_vals = {}

        for idx, lane in enumerate(lanes_set):
            if auto_layout and lane in lane_heights:
                if idx == 0:
                    lane_y_positions[lane] = pool_y
                else:
                    prev_lane = lanes_set[idx - 1]
                    lane_y_positions[lane] = lane_y_positions[prev_lane] + lane_height_vals[prev_lane]
                lane_height_vals[lane] = lane_heights[lane]
            else:
                nids = lane_node_refs[lane]
                if nids:
                    ys = [coords[nid][1] for nid in nids]
                    heights_n = [coords[nid][3] for nid in nids]
                    min_y_l = min(ys)
                    max_y_l = max(ys[i] + heights_n[i] for i in range(len(ys)))
                    lane_y_positions[lane] = min_y_l - 30
                    lane_height_vals[lane] = max(max_y_l - min_y_l + 60, 150)
                else:
                    lane_y_positions[lane] = y_curr
                    lane_height_vals[lane] = 150
                y_curr = lane_y_positions[lane] + lane_height_vals[lane]

        pool_y = lane_y_positions[lanes_set[0]]
        pool_height = sum(lane_height_vals[l] for l in lanes_set)

        collaboration_xml = f'''<bpmn:collaboration id="Collaboration_1">
    <bpmn:participant id="Participant_1" name="Organização" processRef="Process_1" />
  </bpmn:collaboration>'''

        lane_shapes_xml.append(f'''
        <bpmndi:BPMNShape id="Participant_1_di" bpmnElement="Participant_1" isHorizontal="true">
            <dc:Bounds x="{pool_x}" y="{pool_y}" width="{pool_width}" height="{pool_height}" />
        </bpmndi:BPMNShape>
        ''')

        lane_set_entries = []
        for lane in lanes_set:
            lane_id_simplified = f"Lane_{simplify_lane_name(lane)}"
            lane_name_esc = html.escape(lane)
            refs_xml = "\n      ".join(f"<bpmn:flowNodeRef>{nid}</bpmn:flowNodeRef>" for nid in lane_node_refs[lane])
            lane_set_entries.append(f'''<bpmn:lane id="{lane_id_simplified}" name="{lane_name_esc}">
      {refs_xml}
    </bpmn:lane>''')

            lx = pool_x + 30
            ly = lane_y_positions[lane]
            lw = pool_width - 30
            lh = lane_height_vals[lane]

            lane_shapes_xml.append(f'''
        <bpmndi:BPMNShape id="{lane_id_simplified}_di" bpmnElement="{lane_id_simplified}" isHorizontal="true">
            <dc:Bounds x="{lx}" y="{ly}" width="{lw}" height="{lh}" />
        </bpmndi:BPMNShape>
            ''')

        lane_set_xml = f'''<bpmn:laneSet id="LaneSet_1">
    {"".join(lane_set_entries)}
  </bpmn:laneSet>'''
        xml_process.insert(0, lane_set_xml)

    process_xml = "\n    ".join(xml_process)

    if has_lanes:
        diagram_xml = "\n    ".join(lane_shapes_xml) + "\n    " + "\n    ".join(xml_diagram)
    else:
        diagram_xml = "\n    ".join(xml_diagram)

    collab_part = f"\n  {collaboration_xml}\n" if has_lanes else ""

    full_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" 
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" 
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" 
                  xmlns:di="http://www.omg.org/spec/DD/20100524/DI" 
                  id="Definitions_1" 
                  targetNamespace="http://bpmn.io/schema/bpmn">{collab_part}
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