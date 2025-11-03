# app.py
import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from flask_cors import CORS
from auth import requires_auth, register_auth_error_handlers

load_dotenv()

app = Flask(__name__)
CORS(app, origins=os.getenv("FRONTEND_ORIGINS", "*"))

app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/tarefasdb")
mongo = PyMongo(app)

register_auth_error_handlers(app)

@app.route("/tarefas", methods=["GET"])
@requires_auth()  # exige token
def listar_tarefas():
    tarefas = mongo.db.tarefas.find()
    saida = []
    for tarefa in tarefas:
        saida.append({
            "id": str(tarefa["_id"]),
            "titulo": tarefa.get("titulo"),
            "descricao": tarefa.get("descricao"),
            "concluida": tarefa.get("concluida", False)
        })
    return jsonify(saida), 200

@app.route("/tarefas", methods=["POST"])
@requires_auth(required_scope="create:tasks")  # exemplo de scope
def criar_tarefa():
    dados = request.json
    if not dados or "titulo" not in dados or "descricao" not in dados:
        return jsonify({"erro": "Campos 'titulo' e 'descricao' são obrigatórios"}), 400

    tarefa = {
        "titulo": dados["titulo"],
        "descricao": dados["descricao"],
        "concluida": dados.get("concluida", False),
        "criado_em": datetime.utcnow()
    }
    tarefa_id = mongo.db.tarefas.insert_one(tarefa).inserted_id

    return jsonify({
        "id": str(tarefa_id),
        "titulo": tarefa["titulo"],
        "descricao": tarefa["descricao"],
        "concluida": tarefa["concluida"]
    }), 201

@app.route("/tarefas/<id>", methods=["PUT"])
@requires_auth(required_scope="update:tasks")
def atualizar_tarefa(id):
    try:
        _id = ObjectId(id)
    except InvalidId:
        return jsonify({"erro": "ID inválido"}), 400

    dados = request.json or {}
    atualizada = mongo.db.tarefas.find_one_and_update(
        {"_id": _id},
        {"$set": {
            "titulo": dados.get("titulo"),
            "descricao": dados.get("descricao"),
            "concluida": dados.get("concluida", False)
        }},
        return_document=ReturnDocument.AFTER
    )
    if not atualizada:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return jsonify({
        "id": str(atualizada["_id"]),
        "titulo": atualizada["titulo"],
        "descricao": atualizada["descricao"],
        "concluida": atualizada.get("concluida", False)
    }), 200

@app.route("/tarefas/<id>", methods=["DELETE"])
@requires_auth(required_scope="delete:tasks")
def deletar_tarefa(id):
    try:
        _id = ObjectId(id)
    except InvalidId:
        return jsonify({"erro": "ID inválido"}), 400

    resultado = mongo.db.tarefas.delete_one({"_id": _id})
    if resultado.deleted_count == 0:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return jsonify({"mensagem": "Tarefa deletada com sucesso"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
