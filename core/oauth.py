"""LTHub OAuth 2.0 provider for first-party clients (GAL).

Implements the authorization-code flow with PKCE for public clients:

    GET  /oauth/authorize          consent page (uses the LThub web session)
    POST /api/oauth/authorize      issue a short-lived code
    POST /oauth/token              exchange code + code_verifier for a token
    GET  /oauth/userinfo           resolve a token to a user profile

The provider is intentionally self-contained: the routes are registered by
``register_oauth`` from ``api/index.py``, which passes the existing DB/session
helpers. Tables are created lazily and are only reachable through this module;
all tokens/codes are stored as SHA-256 hashes.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode

from flask import jsonify, redirect, request
from sqlalchemy import text

OAUTH_SCOPE = "profile"
CODE_TTL_SECONDS = 300
TOKEN_TTL_SECONDS = 30 * 86400
DEFAULT_REDIRECT_URIS = (
    "https://gal-inky.vercel.app/auth/lthub/callback",
    "http://127.0.0.1:8000/auth/lthub/callback",
    "http://localhost:8000/auth/lthub/callback",
)
CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{2,64}$")
CHALLENGE_RE = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")


def _now() -> int:
    return int(time.time())


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _clients() -> dict[str, dict]:
    """Client registry. GAL is a public PKCE client, so no secret is stored."""
    redirect_uris = {
        uri.strip()
        for uri in (os.getenv("GAL_OAUTH_REDIRECT_URIS") or "").split(",")
        if uri.strip()
    }
    redirect_uris.update(DEFAULT_REDIRECT_URIS)
    extra = os.getenv("GAL_OAUTH_REDIRECT_URI")
    if extra:
        redirect_uris.add(extra.strip())
    return {
        "gal": {
            "name": "Global Achievement List",
            "redirect_uris": redirect_uris,
            "public": True,
        }
    }


def _ensure_tables(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS oauth_codes (
                    code_hash TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    user_id BIGINT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    code_challenge TEXT NOT NULL,
                    expires_at BIGINT NOT NULL,
                    used_at BIGINT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    token_hash TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    user_id BIGINT NOT NULL,
                    created_at BIGINT NOT NULL,
                    expires_at BIGINT NOT NULL,
                    revoked_at BIGINT
                )
                """
            )
        )


def _validate_authorize(
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
) -> tuple[dict | None, str | None]:
    if not CLIENT_ID_RE.fullmatch(client_id or ""):
        return None, "invalid_client"
    client = _clients().get(client_id)
    if client is None:
        return None, "invalid_client"
    if redirect_uri not in client["redirect_uris"]:
        return None, "invalid_redirect_uri"
    if not CHALLENGE_RE.fullmatch(code_challenge or ""):
        return None, "invalid_code_challenge"
    if code_challenge_method != "S256":
        return None, "invalid_code_challenge_method"
    return client, None


def _error_page(message: str, status: int = 400):
    return (
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        "<title>LTHub OAuth</title>"
        '<body style="font-family:system-ui;background:#0f1115;color:#e6e9ef;'
        'display:flex;align-items:center;justify-content:center;min-height:100vh">'
        f'<main style="max-width:520px;padding:24px;border:1px solid #262c38;'
        f'border-radius:12px;background:#171a21"><h1>Ошибка авторизации</h1>'
        f'<p style="color:#8b93a3">{html.escape(message)}</p>'
        '<p><a style="color:#4c8dff" href="/">На главную LTHub</a></p>'
        "</main></body></html>",
        status,
    )


def _authorize_page(params: dict) -> str:
    payload = json.dumps(params, ensure_ascii=False).replace("</", "<\\/")
    register_mode = params.get("intent") == "register"
    mode_path = "/register" if register_mode else "/login"
    mode_label = "Зарегистрироваться" if register_mode else "Войти"
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Вход через LTHub</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
background:#0f1115;color:#e6e9ef;min-height:100vh;display:flex;align-items:center;
justify-content:center;padding:20px}}
.card{{width:100%;max-width:430px;background:#171a21;border:1px solid #262c38;
border-radius:14px;padding:28px}}
h1{{font-size:22px;margin:0 0 8px}} p{{color:#8b93a3;line-height:1.5}}
.who{{margin:18px 0;padding:12px 14px;background:#0f1115;border:1px solid #262c38;
border-radius:8px;color:#e6e9ef}}
.btn{{width:100%;padding:13px;border:0;border-radius:9px;background:#2f6fd6;color:#fff;
font-size:15px;font-weight:600;cursor:pointer;margin-top:8px}}
.btn:disabled{{background:#555;cursor:wait}}
.muted{{font-size:13px}}
a{{color:#4c8dff}}
</style>
</head>
<body>
<main class="card">
  <h1>Global Achievement List</h1>
  <p>Приложение запрашивает доступ к вашему аккаунту LTHub: имя и логин. Пароль не передаётся.</p>
  <div class="who" id="who">Проверяем аккаунт…</div>
  <button class="btn" id="approve" disabled>Продолжить</button>
  <p class="muted" id="status"></p>
</main>
<script>
const PARAMS = {payload};
const MODE_PATH = {json.dumps(mode_path)};
const MODE_LABEL = {json.dumps(mode_label)};
const REDIRECT_TO_MODE = MODE_PATH + "?redirect=" + encodeURIComponent(location.pathname + location.search);
const token = localStorage.getItem("web_token");
const who = document.getElementById("who");
const approve = document.getElementById("approve");
const statusEl = document.getElementById("status");

function fail(message) {{
  who.textContent = message;
  statusEl.textContent = "Войдите в LTHub и обновите страницу.";
  statusEl.innerHTML += ' <a href="' + REDIRECT_TO_MODE + '">' + MODE_LABEL + '</a>';
}}

if (!token) {{
  location.replace(REDIRECT_TO_MODE);
}} else {{
  fetch("/api/auth/me", {{headers: {{"X-Auth-Token": token}}}})
    .then(function (r) {{ return r.ok ? r.json() : Promise.reject(new Error("auth")); }})
    .then(function (me) {{
      who.textContent = "Вы вошли как " + (me.display_name || me.login);
      approve.disabled = false;
      approve.onclick = function () {{
        approve.disabled = true;
        statusEl.textContent = "Создаём код авторизации…";
        fetch("/api/oauth/authorize", {{
          method: "POST",
          headers: {{"Content-Type": "application/json", "X-Auth-Token": token}},
          body: JSON.stringify(Object.assign({{token: token}}, PARAMS))
        }}).then(function (r) {{ return r.json(); }}).then(function (data) {{
          if (data.redirect_url) {{ location.href = data.redirect_url; }}
          else {{ fail(data.error || "Не удалось создать код"); }}
        }}).catch(function () {{ fail("Ошибка сети"); }});
      }};
    }})
    .catch(function () {{
      localStorage.removeItem("web_token");
      fail("Сессия LTHub истекла.");
    }});
}}
</script>
</body>
</html>"""


def register_oauth(app, *, get_db_engine, get_session_user, auth_token, log_error=None):
    """Register LTHub OAuth routes on the Flask app."""

    def _log(message: str) -> None:
        if log_error:
            try:
                log_error("OAUTH", "error", message)
            except Exception:
                pass

    def _engine():
        engine = get_db_engine()
        _ensure_tables(engine)
        return engine

    @app.route("/oauth/authorize", methods=["GET"])
    def oauth_authorize_page():
        client_id = (request.args.get("client_id") or "").strip()
        redirect_uri = (request.args.get("redirect_uri") or "").strip()
        code_challenge = (request.args.get("code_challenge") or "").strip()
        code_challenge_method = (
            request.args.get("code_challenge_method") or ""
        ).strip()
        state = (request.args.get("state") or "").strip()[:256]
        response_type = (request.args.get("response_type") or "").strip()
        intent = (request.args.get("intent") or "").strip().lower()
        if intent not in ("", "login", "register"):
            intent = ""
        if response_type != "code":
            return _error_page("response_type должен быть code")
        client, error = _validate_authorize(
            client_id, redirect_uri, code_challenge, code_challenge_method
        )
        if error:
            return _error_page(f"Некорректный запрос: {error}")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
            "response_type": "code",
        }
        if intent:
            params["intent"] = intent
        return _authorize_page(params)

    @app.route("/api/oauth/authorize", methods=["POST"])
    def oauth_authorize_api():
        data = request.get_json(silent=True) or {}
        token = request.headers.get("X-Auth-Token") or data.get("token") or ""
        user = get_session_user(token)
        if not user:
            return jsonify({"error": "auth_required"}), 401
        client_id = str(data.get("client_id") or "").strip()
        redirect_uri = str(data.get("redirect_uri") or "").strip()
        code_challenge = str(data.get("code_challenge") or "").strip()
        code_challenge_method = str(data.get("code_challenge_method") or "").strip()
        state = str(data.get("state") or "").strip()[:256]
        _client, error = _validate_authorize(
            client_id, redirect_uri, code_challenge, code_challenge_method
        )
        if error:
            return jsonify({"error": error}), 400

        code = secrets.token_urlsafe(32)
        now = _now()
        try:
            with _engine().begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO oauth_codes
                            (code_hash, client_id, user_id, redirect_uri,
                             code_challenge, expires_at)
                        VALUES (:code_hash, :client_id, :user_id, :redirect_uri,
                                :code_challenge, :expires_at)
                        """
                    ),
                    {
                        "code_hash": _hash(code),
                        "client_id": client_id,
                        "user_id": int(user["id"]),
                        "redirect_uri": redirect_uri,
                        "code_challenge": code_challenge,
                        "expires_at": now + CODE_TTL_SECONDS,
                    },
                )
                conn.execute(
                    text("DELETE FROM oauth_codes WHERE expires_at < :cutoff"),
                    {"cutoff": now - 86400},
                )
        except Exception as exc:
            _log(f"issue code error: {exc}")
            return jsonify({"error": "server_error"}), 500

        separator = "&" if "?" in redirect_uri else "?"
        query = {"code": code}
        if state:
            query["state"] = state
        return jsonify({"redirect_url": redirect_uri + separator + urlencode(query)})

    @app.route("/oauth/token", methods=["POST"])
    def oauth_token():
        data = request.get_json(silent=True) or request.form or {}
        client_id = str(data.get("client_id") or "").strip()
        code = str(data.get("code") or "").strip()
        redirect_uri = str(data.get("redirect_uri") or "").strip()
        verifier = str(data.get("code_verifier") or "").strip()
        if (data.get("grant_type") or "authorization_code") != "authorization_code":
            return jsonify({"error": "unsupported_grant_type"}), 400
        _client, error = _validate_authorize(client_id, redirect_uri, "x" * 43, "S256")
        if error:
            return jsonify({"error": error}), 400
        if not VERIFIER_RE.fullmatch(verifier):
            return jsonify({"error": "invalid_code_verifier"}), 400

        now = _now()
        try:
            with _engine().begin() as conn:
                row = (
                    conn.execute(
                        text(
                            """
                        SELECT c.user_id, c.client_id, c.redirect_uri,
                               c.code_challenge, c.expires_at, c.used_at,
                               u.login, u.display_name
                        FROM oauth_codes c
                        JOIN web_users u ON u.id = c.user_id
                        WHERE c.code_hash = :code_hash
                        """
                        ),
                        {"code_hash": _hash(code)},
                    )
                    .mappings()
                    .first()
                )
                if not row or row["used_at"] is not None or row["expires_at"] < now:
                    return jsonify({"error": "invalid_grant"}), 400
                if row["client_id"] != client_id or row["redirect_uri"] != redirect_uri:
                    return jsonify({"error": "invalid_grant"}), 400
                if _pkce_challenge(verifier) != row["code_challenge"]:
                    return jsonify({"error": "invalid_code_verifier"}), 400
                updated = conn.execute(
                    text(
                        "UPDATE oauth_codes SET used_at = :now "
                        "WHERE code_hash = :code_hash AND used_at IS NULL"
                    ),
                    {"now": now, "code_hash": _hash(code)},
                )
                if updated.rowcount != 1:
                    return jsonify({"error": "invalid_grant"}), 400

                access_token = secrets.token_urlsafe(32)
                conn.execute(
                    text(
                        """
                        INSERT INTO oauth_tokens
                            (token_hash, client_id, user_id, created_at,
                             expires_at)
                        VALUES (:token_hash, :client_id, :user_id, :created_at,
                                :expires_at)
                        """
                    ),
                    {
                        "token_hash": _hash(access_token),
                        "client_id": client_id,
                        "user_id": int(row["user_id"]),
                        "created_at": now,
                        "expires_at": now + TOKEN_TTL_SECONDS,
                    },
                )
                conn.execute(
                    text("DELETE FROM oauth_tokens WHERE expires_at < :cutoff"),
                    {"cutoff": now - 86400},
                )
        except Exception as exc:
            _log(f"token exchange error: {exc}")
            return jsonify({"error": "server_error"}), 500

        return jsonify(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": TOKEN_TTL_SECONDS,
                "scope": OAUTH_SCOPE,
                "user": {
                    "sub": str(row["user_id"]),
                    "login": row["login"],
                    "display_name": row["display_name"] or row["login"],
                },
            }
        )

    @app.route("/oauth/userinfo", methods=["GET"])
    def oauth_userinfo():
        header = request.headers.get("Authorization") or ""
        if not header.lower().startswith("bearer "):
            return jsonify({"error": "invalid_token"}), 401
        token = header[7:].strip()
        if not token:
            return jsonify({"error": "invalid_token"}), 401
        now = _now()
        try:
            with _engine().connect() as conn:
                row = (
                    conn.execute(
                        text(
                            """
                        SELECT u.id, u.login, u.display_name,
                               t.expires_at, t.revoked_at
                        FROM oauth_tokens t
                        JOIN web_users u ON u.id = t.user_id
                        WHERE t.token_hash = :token_hash
                        """
                        ),
                        {"token_hash": _hash(token)},
                    )
                    .mappings()
                    .first()
                )
        except Exception as exc:
            _log(f"userinfo error: {exc}")
            return jsonify({"error": "server_error"}), 500
        if not row or row["revoked_at"] is not None or row["expires_at"] < now:
            return jsonify({"error": "invalid_token"}), 401
        return jsonify(
            {
                "sub": str(row["id"]),
                "login": row["login"],
                "display_name": row["display_name"] or row["login"],
                "name": row["display_name"] or row["login"],
            }
        )

    @app.route("/.well-known/oauth-authorization-server", methods=["GET"])
    def oauth_metadata():
        base = request.host_url.rstrip("/")
        return jsonify(
            {
                "issuer": base,
                "authorization_endpoint": base + "/oauth/authorize",
                "token_endpoint": base + "/oauth/token",
                "userinfo_endpoint": base + "/oauth/userinfo",
                "scopes_supported": [OAUTH_SCOPE],
                "response_types_supported": ["code"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
            }
        )

    return app
