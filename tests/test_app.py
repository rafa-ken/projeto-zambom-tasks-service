import pytest
import mongomock
import sys
import os
from unittest.mock import patch, MagicMock
from flask import request

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, mongo

@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    
    # Força mongo.db a usar mongomock (banco em memória)
    mongo.cx = mongomock.MongoClient()
    mongo.db = mongo.cx["tarefas_testdb"]

    # Mock Auth0 validation - bypass authentication in tests
    def mock_requires_auth(required_scope=None):
        def decorator(f):
            def wrapper(*args, **kwargs):
                # Simula um usuário autenticado
                request.current_user = {"sub": "test-user"}
                return f(*args, **kwargs)
            wrapper.__name__ = f.__name__
            return wrapper
        return decorator
    
    # Patch the decorator in app module
    monkeypatch.setattr("app.requires_auth_api", mock_requires_auth)

    client = app.test_client()
    yield client
    # limpa depois dos testes
    mongo.db.tarefas.delete_many({})

def test_criar_tarefa(client):
    resposta = client.post(
        "/tarefas",
        json={"titulo": "Minha Tarefa", "descricao": "Conteúdo da tarefa"}
    )
    assert resposta.status_code == 201
    assert resposta.json["titulo"] == "Minha Tarefa"
    assert resposta.json["concluida"] is False

def test_listar_tarefas(client):
    client.post(
        "/tarefas",
        json={"titulo": "Outra Tarefa", "descricao": "Mais conteúdo"}
    )
    resposta = client.get("/tarefas")
    assert resposta.status_code == 200
    assert len(resposta.json) > 0

def test_atualizar_tarefa(client):
    resposta = client.post(
        "/tarefas",
        json={"titulo": "Antiga Tarefa", "descricao": "Velho conteúdo"}
    )
    tarefa_id = resposta.json["id"]
    update_res = client.put(
        f"/tarefas/{tarefa_id}",
        json={"titulo": "Tarefa Atualizada", "descricao": "Novo conteúdo", "concluida": True}
    )
    assert update_res.status_code == 200
    assert update_res.json["titulo"] == "Tarefa Atualizada"
    assert update_res.json["concluida"] is True

def test_deletar_tarefa(client):
    resposta = client.post(
        "/tarefas",
        json={"titulo": "Tarefa Apagar", "descricao": "Deletar depois"}
    )
    tarefa_id = resposta.json["id"]
    delete_res = client.delete(f"/tarefas/{tarefa_id}")
    assert delete_res.status_code == 200
    assert delete_res.json["message"] == "Tarefa deletada com sucesso"
