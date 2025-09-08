import pytest
import mongomock
from app import app, mongo

@pytest.fixture
def client(monkeypatch):
    app.config["TESTING"] = True
    
    # Força mongo.db a usar mongomock (banco em memória)
    mongo.cx = mongomock.MongoClient()
    mongo.db = mongo.cx["tarefas_testdb"]

    client = app.test_client()
    yield client
    # limpa depois dos testes
    mongo.db.tarefas.delete_many({})

def test_criar_tarefa(client):
    resposta = client.post(
        "/tarefas",
        json={"titulo": "Minha Tarefa", "descricao": "Conteúdo da tarefa"},
        headers={"Authorization": "fake-token"}
    )
    assert resposta.status_code == 201
    assert resposta.json["titulo"] == "Minha Tarefa"
    assert resposta.json["concluida"] is False

def test_listar_tarefas(client):
    client.post(
        "/tarefas",
        json={"titulo": "Outra Tarefa", "descricao": "Mais conteúdo"},
        headers={"Authorization": "fake-token"}
    )
    resposta = client.get("/tarefas", headers={"Authorization": "fake-token"})
    assert resposta.status_code == 200
    assert len(resposta.json) > 0

def test_atualizar_tarefa(client):
    resposta = client.post(
        "/tarefas",
        json={"titulo": "Antiga Tarefa", "descricao": "Velho conteúdo"},
        headers={"Authorization": "fake-token"}
    )
    tarefa_id = resposta.json["id"]
    update_res = client.put(
        f"/tarefas/{tarefa_id}",
        json={"titulo": "Tarefa Atualizada", "descricao": "Novo conteúdo", "concluida": True},
        headers={"Authorization": "fake-token"}
    )
    assert update_res.status_code == 200
    assert update_res.json["titulo"] == "Tarefa Atualizada"
    assert update_res.json["concluida"] is True

def test_deletar_tarefa(client):
    resposta = client.post(
        "/tarefas",
        json={"titulo": "Tarefa Apagar", "descricao": "Deletar depois"},
        headers={"Authorization": "fake-token"}
    )
    tarefa_id = resposta.json["id"]
    delete_res = client.delete(f"/tarefas/{tarefa_id}", headers={"Authorization": "fake-token"})
    assert delete_res.status_code == 200
    assert delete_res.json["mensagem"] == "Tarefa deletada com sucesso"
