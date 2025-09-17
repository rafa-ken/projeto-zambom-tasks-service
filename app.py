import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from bson.objectid import ObjectId

# Carregar variáveis do .env
load_dotenv()

app = Flask(__name__)

# Pega o valor do .env ou usa padrão (útil para testes)
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/testdb")

# Inicializa o PyMongo
mongo = PyMongo(app)

# ---------------- ROTAS ---------------- #

# GET - Listar tarefas
@app.route("/tarefas", methods=["GET"])
def listar_tarefas():
    tarefas = mongo.db.tarefas.find()
    saida = []
    for tarefa in tarefas:
        saida.append({
            "id": str(tarefa["_id"]),
            "titulo": tarefa["titulo"],
            "descricao": tarefa["descricao"],
            "concluida": tarefa.get("concluida", False)
        })
    return jsonify(saida), 200

# POST - Criar tarefa
@app.route("/tarefas", methods=["POST"])
def criar_tarefa():
    dados = request.json
    if not dados or "titulo" not in dados or "descricao" not in dados:
        return jsonify({"erro": "Campos 'titulo' e 'descricao' são obrigatórios"}), 400

    tarefa_id = mongo.db.tarefas.insert_one({
        "titulo": dados["titulo"],
        "descricao": dados["descricao"],
        "concluida": dados.get("concluida", False)
    }).inserted_id

    return jsonify({
        "id": str(tarefa_id),
        "titulo": dados["titulo"],
        "descricao": dados["descricao"],
        "concluida": dados.get("concluida", False)
    }), 201

# PUT - Atualizar tarefa
@app.route("/tarefas/<id>", methods=["PUT"])
def atualizar_tarefa(id):
    dados = request.json
    atualizada = mongo.db.tarefas.find_one_and_update(
        {"_id": ObjectId(id)},
        {"$set": {
            "titulo": dados.get("titulo"),
            "descricao": dados.get("descricao"),
            "concluida": dados.get("concluida", False)
        }},
        return_document=True
    )
    if not atualizada:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return jsonify({
        "id": str(atualizada["_id"]),
        "titulo": atualizada["titulo"],
        "descricao": atualizada["descricao"],
        "concluida": atualizada.get("concluida", False)
    }), 200

# DELETE - Remover tarefa
@app.route("/tarefas/<id>", methods=["DELETE"])
def deletar_tarefa(id):
    resultado = mongo.db.tarefas.delete_one({"_id": ObjectId(id)})
    if resultado.deleted_count == 0:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return jsonify({"mensagem": "Tarefa deletada com sucesso"}), 200

# --------------------------------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=True)
