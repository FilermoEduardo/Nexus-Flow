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
