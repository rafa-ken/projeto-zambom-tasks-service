# app.py (tasks service - production-ready, CORS + Auth0 JWKS + logs)
import os
import time
import logging
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, request, jsonify, make_response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from jose import jwt
import requests
from flask_cors import CORS

# Load env
load_dotenv()

# Logger
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("tasks-app")

app = Flask(__name__)

# -------------------------
# App config
# -------------------------
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/tasksdb")

# FRONTEND_ORIGINS: comma separated list OR "*" (like notes service)
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173")
if FRONTEND_ORIGINS.strip() == "*":
    cors_origins = "*"
else:
    cors_origins = [o.strip() for o in FRONTEND_ORIGINS.split(",") if o.strip()]

# Initialize CORS (basic)
CORS(app, origins=cors_origins, supports_credentials=True, allow_headers=["Content-Type", "Authorization"])

# -------------------------
# Auth0 / JWKS config
# -------------------------
# Support either API_AUDIENCE or AUTH0_AUDIENCE env names for convenience
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN") or os.getenv("VITE_AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("API_AUDIENCE") or os.getenv("AUTH0_AUDIENCE") or os.getenv("VITE_AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]

# JWKS cache
_JWKS_CACHE = {"fetched_at": 0, "jwks": None, "ttl": 3600}


def _get_jwks():
    if not AUTH0_DOMAIN:
        raise RuntimeError("AUTH0_DOMAIN não configurado (ver .env)")
    now = time.time()
    if _JWKS_CACHE["jwks"] and now - _JWKS_CACHE["fetched_at"] < _JWKS_CACHE["ttl"]:
        return _JWKS_CACHE["jwks"]
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    r = requests.get(jwks_url, timeout=5)
    r.raise_for_status()
    jwks = r.json()
    _JWKS_CACHE.update({"jwks": jwks, "fetched_at": now})
    return jwks


# -------------------------
# Helpers / Auth decorator
# -------------------------
def requires_auth_api(required_scope: str = None):
    """
    Decorator to require a Bearer access token (Auth0).
    If required_scope is provided, also checks that scope exists in token.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", None)
            if not auth:
                return jsonify({"error": "Authorization header missing"}), 401

            parts = auth.split()
            if parts[0].lower() != "bearer" or len(parts) != 2:
                return jsonify({"error": "Invalid Authorization header"}), 401
            token = parts[1]

            try:
                unverified_header = jwt.get_unverified_header(token)
            except Exception:
                return jsonify({"error": "Invalid token header"}), 401

            try:
                jwks = _get_jwks()
            except Exception as e:
                logger.exception("Failed to fetch JWKS")
                return jsonify({"error": f"Erro ao buscar JWKS: {str(e)}"}), 500

            rsa_key = {}
            for key in jwks.get("keys", []):
                if key.get("kid") == unverified_header.get("kid"):
                    rsa_key = {
                        "kty": key.get("kty"),
                        "kid": key.get("kid"),
                        "use": key.get("use"),
                        "n": key.get("n"),
                        "e": key.get("e")
                    }
                    break

            if not rsa_key:
                return jsonify({"error": "Appropriate JWK not found"}), 401

            try:
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=ALGORITHMS,
                    audience=AUTH0_AUDIENCE,
                    issuer=f"https://{AUTH0_DOMAIN}/"
                )
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except Exception as e:
                logger.warning("Token validation error: %s", e)
                return jsonify({"error": f"Token inválido: {str(e)}"}), 401

            # scope check (optional)
            if required_scope:
                scopes = payload.get("scope", "")
                scopes_list = scopes.split() if isinstance(scopes, str) else []
                if required_scope not in scopes_list:
                    return jsonify({"error": "Insufficient scope"}), 403

            # attach claims
            request.current_user = payload
            return f(*args, **kwargs)
        return decorated
    return decorator


# -------------------------
# DB
# -------------------------
mongo = PyMongo(app)


# -------------------------
# CORS preflight handler + global CORS headers
# -------------------------
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        origin = request.headers.get("Origin")
        allowed_origin = None
        if cors_origins == "*" or (origin and origin in cors_origins):
            allowed_origin = origin if origin else "*"

        resp = make_response("", 204)
        if allowed_origin:
            resp.headers["Access-Control-Allow-Origin"] = allowed_origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
            resp.headers["Access-Control-Allow-Headers"] = "Authorization,Content-Type,Accept"
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Max-Age"] = "3600"
        return resp


@app.before_request
def log_request_info():
    logger.debug("Incoming request: %s %s", request.method, request.path)
    # show only key headers to avoid leaking secrets in logs
    hdrs = {k: v for k, v in request.headers.items() if k in ("Host", "Origin", "Authorization", "Content-Type")}
    logger.debug("Headers: %s", hdrs)
    try:
        logger.debug("Body preview: %s", request.get_data(as_text=True)[:1000])
    except Exception:
        pass


@app.after_request
def after_request(response):
    origin = request.headers.get("Origin")
    if origin:
        if cors_origins == "*" or origin in cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin if cors_origins != "*" else "*"
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,Accept"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Max-Age"] = "3600"
    return response


# -------------------------
# Routes
# -------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "tasks"}), 200


@app.route("/tarefas", methods=["GET"])
@requires_auth_api()  # you can pass required_scope="read:tasks" if you want scope checking
def listar_tarefas():
    tarefas = mongo.db.tarefas.find()
    out = []
    for t in tarefas:
        out.append({
            "id": str(t["_id"]),
            "titulo": t.get("titulo"),
            "descricao": t.get("descricao"),
            "concluida": t.get("concluida", False)
        })
    return jsonify(out), 200


@app.route("/tarefas", methods=["POST"])
@requires_auth_api(required_scope="create:tasks")
def criar_tarefa():
    dados = request.json
    if not dados or "descricao" not in dados:
        return jsonify({"error": "Campo 'descricao' é obrigatório"}), 400

    tarefa_doc = {
        "titulo": dados.get("titulo", ""),  # titulo agora é opcional
        "descricao": dados["descricao"],
        "concluida": dados.get("concluida", False),
        # optional: "owner": request.current_user.get("sub")
    }
    tarefa_id = mongo.db.tarefas.insert_one(tarefa_doc).inserted_id

    return jsonify({
        "id": str(tarefa_id),
        "titulo": tarefa_doc["titulo"],
        "descricao": tarefa_doc["descricao"],
        "concluida": tarefa_doc["concluida"]
    }), 201


@app.route("/tarefas/<id>", methods=["PUT"])
@requires_auth_api(required_scope="update:tasks")
def atualizar_tarefa(id):
    dados = request.json or {}
    try:
        obj_id = ObjectId(id)
    except Exception:
        return jsonify({"error": "ID inválido"}), 400

    update_fields = {}
    if "titulo" in dados:
        update_fields["titulo"] = dados["titulo"]
    if "descricao" in dados:
        update_fields["descricao"] = dados["descricao"]
    if "concluida" in dados:
        update_fields["concluida"] = dados["concluida"]
    
    atualizada = mongo.db.tarefas.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER
    )
    if not atualizada:
        return jsonify({"error": "Tarefa não encontrada"}), 404

    return jsonify({
        "id": str(atualizada["_id"]),
        "titulo": atualizada.get("titulo"),
        "descricao": atualizada.get("descricao"),
        "concluida": atualizada.get("concluida", False)
    }), 200


@app.route("/tarefas/<id>", methods=["DELETE"])
@requires_auth_api(required_scope="delete:tasks")
def deletar_tarefa(id):
    try:
        obj_id = ObjectId(id)
    except Exception:
        return jsonify({"error": "ID inválido"}), 400

    resultado = mongo.db.tarefas.delete_one({"_id": obj_id})
    if resultado.deleted_count == 0:
        return jsonify({"error": "Tarefa não encontrada"}), 404
    return jsonify({"message": "Tarefa deletada com sucesso"}), 200


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("FLASK_RUN_PORT", 5000)))
    debug_flag = (os.getenv("FLASK_DEBUG", "false").lower() == "true")
    app.run(host="0.0.0.0", port=port, debug=debug_flag)