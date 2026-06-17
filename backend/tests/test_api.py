import sys
import os
import json
import pytest

# Adiciona o diretório backend ao path para conseguir importar a app Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_upload_schema_validation_invalid(client):
    # Envia um JSON que não obedece ao schema (falta o id de um nó, e flow não é lista)
    response = client.post('/upload', json={
        "flow": {
            "id": 1,
            "name": "teste"
        }
    })
    
    assert response.status_code == 400
    data = json.loads(response.data.decode('utf-8'))
    assert "error" in data

def test_api_upload_schema_validation_valid(client):
    # Envia um JSON correto e espera status 200 e XML de retorno
    response = client.post('/upload', json={
        "flow": [
            {
                "id": 1,
                "parent": None,
                "edge": 0,
                "cod_componente": 1,
                "name": "Inicio"
            }
        ]
    })
    
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/xml'
    assert b"bpmn:startEvent" in response.data

def test_api_chat_validation_missing_question(client):
    # Envia dados sem o parâmetro question
    response = client.post('/chat', json={
        "flow_data": []
    })
    
    assert response.status_code == 400
    data = json.loads(response.data.decode('utf-8'))
    assert "error" in data
    assert "question" in data["error"]

def test_api_refine_flow_missing_params(client):
    # Envia sem o parâmetro instruction ou flow
    response = client.post('/refine-flow', json={
        "instruction": "Adicionar nó"
    })
    
    assert response.status_code == 400
    data = json.loads(response.data.decode('utf-8'))
    assert "error" in data


def test_api_upload_evolved_schema_valid(client):
    # Envia um JSON com o schema evoluído (lane, task_type, event_type) e espera status 200
    payload = {
        "flow": [
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
            }
        ]
    }
    response = client.post('/upload', json=payload)
    
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/xml'
    xml_data = response.data.decode('utf-8')
    assert "Participant_1" in xml_data
    assert "Lane_Atendimento" in xml_data
    assert "Lane_Suporte_Tecnico" in xml_data
    assert "bpmn:userTask" in xml_data
    assert "bpmn:timerEventDefinition" in xml_data
