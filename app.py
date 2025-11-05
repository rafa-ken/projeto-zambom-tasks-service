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

# Optional: RabbitMQ publisher
try:
    import pika
except Exception:
    pika = None

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
app.config["AUTH0_DOMAIN"] = os.getenv("AUTH0_DOMAIN")
app.config["AUTH0_AUDIENCE"] = os.getenv("API_AUDIENCE") or os.getenv("AUTH0_AUDIENCE")

# FRONTEND_ORIGINS: comma separated list OR "*" (like notes service)
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173")
if FRONTEND_ORIGINS.strip() == "*":
    cors_origins = "*"
else:
    cors_origins = [o.strip() for o in FRONTEND_ORIGINS.split(",") if o.strip()]

# Initialize CORS with full configuration
CORS(app,
     resources={r"/*": {"origins": cors_origins}},
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "Accept"],
     expose_headers=["Content-Type"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

# -------------------------
# Auth0 / JWKS config
# -------------------------
AUTH0_DOMAIN = app.config.get("AUTH0_DOMAIN")
AUTH0_AUDIENCE = app.config.get("AUTH0_AUDIENCE")
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
    Bypasses authentication when app.config['TESTING'] is True.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Bypass authentication in test mode
            if app.config.get("TESTING"):
                request.current_user = {"sub": "test-user"}
                return f(*args, **kwargs)

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
                # Se JWKS falhar e já tivermos cache vazio — erro 500
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
# RabbitMQ publisher (opcional)
# -------------------------
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
_rabbit_channel = None

def _ensure_rabbit():
    global _rabbit_channel
    if not RABBITMQ_URL or not pika:
        return None
    if _rabbit_channel:
        return _rabbit_channel
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.exchange_declare(exchange="app.events", exchange_type="topic", durable=True)
        _rabbit_channel = ch
        return ch
    except Exception as e:
        logger.warning("RabbitMQ unavailable: %s", e)
        return None

def publish_event(event_type, payload):
    ch = _ensure_rabbit()
    event = {
        "event_id": str(ObjectId()),
        "event_type": event_type,
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "payload": payload
    }
    if ch:
        try:
            ch.basic_publish(
                exchange="app.events",
                routing_key=event_type,
                body=jsonify(event).get_data(as_text=True),
                properties=pika.BasicProperties(content_type='application/json', delivery_mode=2)
            )
            logger.debug("Published event %s", event_type)
        except Exception as e:
            logger.warning("Failed to publish event: %s", e)
    else:
        logger.debug("No rabbit channel configured; skipping publish for %s", event_type)


# -------------------------
# Logging
# -------------------------
@app.before_request
def log_request_info():
    logger.debug("Incoming request: %s %s", request.method, request.path)
    # NÃO logar Authorization
    hdrs = {k: v for k, v in request.headers.items() if k in ("Host", "Origin", "Content-Type")}
    logger.debug("Headers: %s", hdrs)
    try:
        logger.debug("Body preview: %s", request.get_data(as_text=True)[:1000])
    except Exception:
        pass


# -------------------------
# Helpers: idempotency util
# -------------------------
def get_idempotency_record(collection_name, idempotency_key):
    if not idempotency_key:
        return None
    return mongo.db.idempotency.find_one({"collection": collection_name, "idempotency_key": idempotency_key})

def save_idempotency_record(collection_name, idempotency_key, resource):
    if not idempotency_key:
        return
    mongo.db.idempotency.replace_one(
        {"collection": collection_name, "idempotency_key": idempotency_key},
        {"collection": collection_name, "idempotency_key": idempotency_key, "resource": resource},
        upsert=True
    )


# -------------------------
# Routes
# -------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "tasks"}), 200

@app.route("/ready", methods=["GET"])
def ready():
    try:
        mongo.db.command("ping")
        return jsonify({"ready": True}), 200
    except Exception:
        return jsonify({"ready": False}), 503


@app.route("/tarefas", methods=["GET"])
@requires_auth_api()
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
@requires_auth_api()  # TEMPORÁRIO: scope removido para testes
def criar_tarefa():
    dados = request.json
    if not dados or "descricao" not in dados:
        return jsonify({"error": "Campo 'descricao' é obrigatório"}), 400

    idempotency_key = request.headers.get("Idempotency-Key")
    existing = get_idempotency_record("tarefas", idempotency_key)
    if existing:
        return jsonify(existing["resource"]), 200

    tarefa_doc = {
        "titulo": dados.get("titulo", ""),  # titulo agora é opcional
        "descricao": dados["descricao"],
        "concluida": dados.get("concluida", False),
        "owner": request.current_user.get("sub") if hasattr(request, "current_user") else None,
        "criado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "atualizado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    tarefa_id = mongo.db.tarefas.insert_one(tarefa_doc).inserted_id

    # Também gravar um snapshot para validações futuras por outros serviços
    try:
        snapshot = {
            "_id": tarefa_id,
            "titulo": tarefa_doc["titulo"],
            "descricao": tarefa_doc["descricao"],
            "owner": tarefa_doc["owner"],
            "status": "open",
            "criado_em": tarefa_doc["criado_em"],
            "atualizado_em": tarefa_doc["atualizado_em"]
        }
        mongo.db.task_snapshots.replace_one({"_id": tarefa_id}, snapshot, upsert=True)
    except Exception as e:
        logger.warning("Falha ao gravar snapshot de task: %s", e)

    resource = {
        "id": str(tarefa_id),
        "titulo": tarefa_doc["titulo"],
        "descricao": tarefa_doc["descricao"],
        "concluida": tarefa_doc["concluida"]
    }

    # event publish (opcional)
    try:
        # publish_event("task.created", {...})  # opcional; deixei comentado por segurança
        pass
    except Exception:
        logger.exception("Erro ao publicar evento task.created")

    save_idempotency_record("tarefas", idempotency_key, resource)

    return jsonify(resource), 201


@app.route("/tarefas/<id>", methods=["PUT"])
@requires_auth_api()  # TEMPORÁRIO: scope removido para testes
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

    update_fields["atualizado_em"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    atualizada = mongo.db.tarefas.find_one_and_update(
        {"_id": obj_id},
        {"$set": update_fields},
        return_document=ReturnDocument.AFTER
    )
    if not atualizada:
        return jsonify({"error": "Tarefa não encontrada"}), 404

    # atualizar snapshot também
    try:
        mongo.db.task_snapshots.update_one({"_id": obj_id}, {"$set": {
            "titulo": atualizada.get("titulo"),
            "descricao": atualizada.get("descricao"),
            "status": "open" if not atualizada.get("concluida") else "done",
            "atualizado_em": update_fields["atualizado_em"]
        }}, upsert=True)
    except Exception as e:
        logger.warning("Falha ao atualizar snapshot: %s", e)

    return jsonify({
        "id": str(atualizada["_id"]),
        "titulo": atualizada.get("titulo"),
        "descricao": atualizada.get("descricao"),
        "concluida": atualizada.get("concluida", False)
    }), 200


@app.route("/tarefas/<id>", methods=["DELETE"])
@requires_auth_api()  # TEMPORÁRIO: scope removido para testes
def deletar_tarefa(id):
    try:
        obj_id = ObjectId(id)
    except Exception:
        return jsonify({"error": "ID inválido"}), 400

    resultado = mongo.db.tarefas.delete_one({"_id": obj_id})
    if resultado.deleted_count == 0:
        return jsonify({"error": "Tarefa não encontrada"}), 404

    # remover snapshot (ou marcar soft-delete conforme política)
    try:
        mongo.db.task_snapshots.delete_one({"_id": obj_id})
    except Exception as e:
        logger.warning("Falha ao deletar snapshot: %s", e)

    return jsonify({"message": "Tarefa deletada com sucesso"}), 200


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    # criar índices básicos
    try:
        mongo.db.tarefas.create_index("owner")
        mongo.db.task_snapshots.create_index("owner")
        mongo.db.idempotency.create_index([("collection", 1), ("idempotency_key", 1)], unique=True, sparse=True)
    except Exception:
        logger.warning("Falha ao criar índices iniciais")

    port = int(os.getenv("PORT", os.getenv("FLASK_RUN_PORT", 5000)))
    debug_flag = (os.getenv("FLASK_DEBUG", "false").lower() == "true")
    app.run(host="0.0.0.0", port=port, debug=debug_flag)
