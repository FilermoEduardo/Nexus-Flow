import sys
import os
import xml.etree.ElementTree as ET

# Adiciona o diretório backend ao path para conseguir importar translator
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from translator import generate_bpmn_xml

def test_generate_bpmn_xml_simple():
    # Fluxo simples: Início -> Tarefa -> Fim
    flow_data = [
        {
            "id": 1,
            "parent": None,
            "edge": 0,
            "cod_componente": 1,
            "name": "Inicio do Fluxo"
        },
        {
            "id": 2,
            "parent": 1,
            "edge": 0,
            "cod_componente": 17,
            "name": "Mensagem de Boas-vindas"
        },
        {
            "id": 3,
            "parent": 2,
            "edge": 0,
            "cod_componente": 1,
            "name": "Fim do Fluxo"
        }
    ]

    xml_output = generate_bpmn_xml(flow_data, auto_layout=True)

    # Verifica se gerou conteúdo
    assert xml_output is not None
    assert "<?xml version=" in xml_output
    assert "<bpmn:definitions" in xml_output
    assert "node_1" in xml_output
    assert "node_2" in xml_output
    assert "node_3" in xml_output

    # Parseia para validar a sintaxe XML
    try:
        # Registra namespaces comuns do bpmn para evitar quebra no parse
        namespaces = {
            'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
            'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
            'dc': 'http://www.omg.org/spec/DD/20100524/DC',
            'di': 'http://www.omg.org/spec/DD/20100524/DI'
        }
        for prefix, uri in namespaces.items():
            ET.register_namespace(prefix, uri)
            
        root = ET.fromstring(xml_output)
        assert root.tag.endswith('definitions')
    except Exception as e:
        assert False, f"O XML gerado é inválido sintaticamente: {e}"


def test_generate_bpmn_xml_evolved():
    # Fluxo evoluído com raias (lanes), task_type e event_type
    flow_data = [
        {
            "id": 1,
            "parent": None,
            "edge": 0,
            "cod_componente": 1,
            "name": "Iniciado",
            "lane": "Atendimento"
        },
        {
            "id": 2,
            "parent": 1,
            "edge": 0,
            "cod_componente": 17,
            "task_type": "user",
            "name": "Verificar histórico",
            "lane": "Suporte Técnico"
        },
        {
            "id": 3,
            "parent": 2,
            "edge": 0,
            "cod_componente": 11,
            "event_type": "timer",
            "name": "Aguardado 5 minutos",
            "lane": "Suporte Técnico"
        },
        {
            "id": 4,
            "parent": 3,
            "edge": 0,
            "cod_componente": 17,
            "task_type": "service",
            "name": "Enviar log",
            "lane": "Geral"
        },
        {
            "id": 5,
            "parent": 4,
            "edge": 0,
            "cod_componente": 1,
            "event_type": "terminate",
            "name": "Finalizado",
            "lane": "Geral"
        }
    ]

    xml_output = generate_bpmn_xml(flow_data, auto_layout=True)

    # Verifica se gerou o XML correto
    assert xml_output is not None
    assert "Collaboration_1" in xml_output
    assert "Participant_1" in xml_output
    assert "Lane_Atendimento" in xml_output
    assert "Lane_Suporte_Tecnico" in xml_output
    assert "Lane_Geral" in xml_output
    assert "bpmn:userTask" in xml_output
    assert "bpmn:serviceTask" in xml_output
    assert "bpmn:timerEventDefinition" in xml_output
    assert "bpmn:terminateEventDefinition" in xml_output

    # Parseia para validar a sintaxe
    try:
        root = ET.fromstring(xml_output)
        assert root.tag.endswith('definitions')
    except Exception as e:
        assert False, f"O XML gerado com lanes é inválido sintaticamente: {e}"

def test_generate_bpmn_xml_explicit_edges():
    # Teste de convergência / ramificação usando conexões explícitas (edge: 1) e labels
    flow_data = [
        {
            "id": 1,
            "parent": None,
            "edge": 0,
            "cod_componente": 1,
            "name": "Iniciado"
        },
        {
            "id": 2,
            "parent": 1,
            "edge": 0,
            "cod_componente": 15,
            "name": "Verificar decisão"
        },
        {
            "id": 3,
            "parent": None, # Sem parent direto, conectado via edge explícita
            "edge": 0,
            "cod_componente": 17,
            "task_type": "service",
            "name": "Executar rota A"
        },
        {
            "id": "edge_decisao",
            "edge": 1,
            "source": 2,
            "target": 3,
            "value": "Opcao A"
        }
    ]
    xml_output = generate_bpmn_xml(flow_data, auto_layout=True)
    assert xml_output is not None
    assert 'name="Opcao A"' in xml_output
    assert 'sourceRef="node_2"' in xml_output
    assert 'targetRef="node_3"' in xml_output
    assert 'BPMNLabel' in xml_output
