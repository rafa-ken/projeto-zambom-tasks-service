# auth.py
import os
import time
from functools import wraps
from urllib.parse import urlencode

import requests
from authlib.integrations.flask_client import OAuth
from flask import session, redirect, url_for, request, jsonify, current_app
from jose import jwt

# Load env
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET")
AUTH0_CALLBACK_URL = os.environ.get("AUTH0_CALLBACK_URL")  # e.g. http://localhost:5000/callback
API_AUDIENCE = os.environ.get("AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]

# OAuth client (interactive login)
def init_oauth(app):
    oauth = OAuth(app)
    oauth.register(
        name="auth0",
        client_id=AUTH0_CLIENT_ID,
        client_secret=AUTH0_CLIENT_SECRET,
        client_kwargs={
            "scope": "openid profile email",
        },
        server_metadata_url=f"https://{AUTH0_DOMAIN}/.well-known/openid-configuration",
    )
    return oauth

# --- JWT validation for API endpoints (resource server) ---
_JWKS_CACHE = {"fetched_at": 0, "jwks": None, "ttl": 3600}

def _get_jwks():
    now = time.time()
    if _JWKS_CACHE["jwks"] and now - _JWKS_CACHE["fetched_at"] < _JWKS_CACHE["ttl"]:
        return _JWKS_CACHE["jwks"]
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    r = requests.get(jwks_url, timeout=5)
    r.raise_for_status()
    jwks = r.json()
    _JWKS_CACHE.update({"jwks": jwks, "fetched_at": now})
    return jwks

def requires_auth_api(f):
    """
    Decorator to protect API endpoints expecting a Bearer access token issued by Auth0.
    Validates signature, issuer and audience.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", None)
        if not auth:
            return jsonify({"message":"Authorization header missing"}), 401
        parts = auth.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            return jsonify({"message":"Invalid Authorization header"}), 401
        token = parts[1]

        try:
            unverified_header = jwt.get_unverified_header(token)
        except Exception:
            return jsonify({"message":"Invalid token header"}), 401

        rsa_key = {}
        jwks = _get_jwks()
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = {
                    "kty": key.get("kty"),
                    "kid": key.get("kid"),
                    "use": key.get("use"),
                    "n": key.get("n"),
                    "e": key.get("e"),
                }
        if not rsa_key:
            return jsonify({"message":"Appropriate JWK not found"}), 401

        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=API_AUDIENCE,
                issuer=f"https://{AUTH0_DOMAIN}/"
            )
        except Exception as e:
            return jsonify({"message": f"Token validation error: {str(e)}"}), 401

        # Attach user info to flask.g or session if you want
        request.current_user = payload
        return f(*args, **kwargs)
    return decorated

# --- Helper for interactive login routes (optional) ---
def login_redirect(oauth):
    return oauth.auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL, audience=API_AUDIENCE)

def handle_callback(oauth):
    token = oauth.auth0.authorize_access_token()
    userinfo = oauth.auth0.parse_id_token(token)
    # Store minimal user in session
    session['user'] = {
        "sub": userinfo.get("sub"),
        "name": userinfo.get("name"),
        "email": userinfo.get("email"),
    }
    # Optionally store access token if you want server to call other APIs
    session['access_token'] = token.get("access_token")
    return session['user']
