"""Sign in / sign up to LTHub through GAL (OAuth 2.0 code + PKCE).

GAL is a public PKCE client, so no secret is stored. A one-time ``state`` and
the code verifier live in HttpOnly cookies; the callback creates a LTHub
account from the GAL profile (login + display name) or reuses the account
linked by ``web_users.gal_subject``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
from urllib.parse import quote, urlencode

import requests
from flask import jsonify, redirect, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

STATE_COOKIE = "gal_oauth_state"
VERIFIER_COOKIE = "gal_oauth_verifier"
NEXT_COOKIE = "gal_oauth_next"
TOKEN_COOKIE = "gal_oauth_token"
COOKIE_MAX_AGE = 600
TOKEN_COOKIE_MAX_AGE = 120
CALLBACK_PATH = "/api/auth/gal/callback"
DONE_PATH = "/auth/gal/done"
SESSION_PATH = "/api/auth/gal/session"
LOGIN_SCOPE = "profile"
LOGIN_RE = re.compile(r"^[a-z0-9_]{3,64}$")


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _flag(name: str, default: str = "true") -> bool:
    return (os.getenv(name) or default).strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _config() -> dict:
    return {
        "enabled": _flag("GAL_OAUTH_ENABLED"),
        "client_id": (os.getenv("GAL_OAUTH_CLIENT_ID") or "lthub").strip() or "lthub",
        "authorize_url": (
            os.getenv("GAL_OAUTH_AUTHORIZE_URL")
            or "https://gal-inky.vercel.app/oauth/authorize"
        ).strip(),
        "token_url": (
            os.getenv("GAL_OAUTH_TOKEN_URL")
            or "https://gal-inky.vercel.app/oauth/token"
        ).strip(),
        "userinfo_url": (
            os.getenv("GAL_OAUTH_USERINFO_URL")
            or "https://gal-inky.vercel.app/oauth/userinfo"
        ).strip(),
    }


def _redirect_uri() -> str:
    configured = (os.getenv("GAL_OAUTH_REDIRECT_URI") or "").strip()
    if configured:
        return configured
    return request.url_root.rstrip("/") + CALLBACK_PATH


def _safe_next(value: str | None) -> str:
    target = (value or "").strip()
    if not target.startswith("/") or target.startswith("//"):
        return "/"
    # Браузеры трактуют "\" как "/", поэтому "/\evil.com" — внешний редирект.
    if "\\" in target or any(c in target for c in ("\r", "\n", "\t")):
        return "/"
    if target.startswith(("/auth/gal", "/api/auth/gal")):
        return "/"
    return target


def _cookie_kwargs(max_age: int) -> dict:
    return {
        "max_age": max_age,
        "path": "/",
        "httponly": True,
        "samesite": "lax",
        "secure": request.is_secure,
    }


def _clear_flow_cookies(response) -> None:
    for name in (STATE_COOKIE, VERIFIER_COOKIE, NEXT_COOKIE):
        response.delete_cookie(name, path="/")


def _error_page(title: str, message: str, status: int = 400):
    body = (
        '<!doctype html><html lang="ru"><meta charset="utf-8">'
        f"<title>{html.escape(title)} — LTHub</title>"
        '<body style="font-family:system-ui;background:#0f1115;color:#e6e9ef;'
        'display:flex;align-items:center;justify-content:center;min-height:100vh">'
        '<main style="max-width:520px;padding:24px;border:1px solid #262c38;'
        'border-radius:12px;background:#171a21">'
        f"<h1>{html.escape(title)}</h1>"
        f'<p style="color:#8b93a3">{html.escape(message)}</p>'
        '<p><a style="color:#4c8dff" href="/login">Вернуться ко входу</a> · '
        '<a style="color:#4c8dff" href="/register">Регистрация</a></p>'
        "</main></body></html>"
    )
    return body, status


def _done_page(redirect_to: str) -> str:
    target = json.dumps(redirect_to).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Вход через GAL — LTHub</title>
<style>
body{{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
background:#0f1115;color:#e6e9ef;min-height:100vh;display:flex;align-items:center;
justify-content:center}}
main{{max-width:420px;padding:24px;text-align:center}}
p{{color:#8b93a3}}
</style>
</head>
<body>
<main>
<h1>Вход через GAL</h1>
<p id="status">Завершаем вход…</p>
</main>
<script>
const TARGET = {target};
fetch("/api/auth/gal/session", {{credentials: "same-origin", cache: "no-store"}})
  .then(function (r) {{ return r.ok ? r.json() : Promise.reject(new Error("session")); }})
  .then(function (data) {{
    if (!data.token) {{ throw new Error("token"); }}
    localStorage.setItem("web_token", data.token);
    if (data.user_id) {{ localStorage.setItem("web_user_id", "u" + data.user_id); }}
    location.replace(TARGET);
  }})
  .catch(function () {{
    document.getElementById("status").textContent =
      "Не удалось завершить вход. Попробуйте ещё раз.";
  }});
</script>
</body>
</html>"""


def sanitize_login(value: str, subject: str) -> str:
    base = re.sub(r"[^a-z0-9_]+", "_", (value or "").strip().lower()).strip("_")
    base = base[:64]
    if len(base) >= 3:
        return base
    digest = hashlib.sha256((subject or "gal").encode("utf-8")).hexdigest()[:8]
    return f"gal_{digest}"


def _login_candidates(base: str) -> list[str]:
    candidates = [base]
    stem = base[:60].rstrip("_") or "gal"
    candidates.extend(f"{stem}_{index}" for index in range(2, 10))
    candidates.append(f"{stem[:48]}_{secrets.token_hex(3)}")
    return candidates


def _find_linked_user(conn, subject: str):
    return (
        conn.execute(
            text(
                "SELECT id, login, display_name FROM web_users "
                "WHERE gal_subject = :subject"
            ),
            {"subject": subject},
        )
        .mappings()
        .first()
    )


def _create_or_get_user(
    conn, *, subject: str, username: str, display_name: str, hash_password
):
    linked = _find_linked_user(conn, subject)
    if linked:
        return linked, False

    login = sanitize_login(username, subject)
    for candidate in _login_candidates(login):
        if conn.execute(
            text("SELECT 1 FROM web_users WHERE login = :login"), {"login": candidate}
        ).first():
            continue
        try:
            with conn.begin_nested():
                row = (
                    conn.execute(
                        text(
                            """
                        INSERT INTO web_users
                            (login, password_hash, display_name, created_via,
                             gal_subject, gal_username)
                        VALUES (:login, :password_hash, :display_name, 'gal_oauth',
                                :subject, :username)
                        RETURNING id, login, display_name
                        """
                        ),
                        {
                            "login": candidate,
                            "password_hash": hash_password(secrets.token_urlsafe(32)),
                            "display_name": display_name,
                            "subject": subject,
                            "username": username,
                        },
                    )
                    .mappings()
                    .first()
                )
            return row, True
        except IntegrityError:
            # Concurrent callback or login race: reuse the linked row if the
            # other request won, otherwise try the next login candidate.
            linked = _find_linked_user(conn, subject)
            if linked:
                return linked, False
    raise RuntimeError("Не удалось подобрать свободный логин")


def _ensure_gal_columns(engine) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_web_users_gal_subject "
                    "ON web_users (gal_subject)"
                )
            )
    except Exception as exc:  # noqa: BLE001 - optional index on legacy schemas
        logger.debug("GAL OAuth index creation skipped: %s", exc)


def register_gal_oauth(
    app,
    *,
    get_db_engine,
    create_session,
    hash_password,
    ensure_columns=None,
    award_coins=None,
    log_error=None,
):
    """Register GAL OAuth client routes on the Flask app."""

    def _log(message: str) -> None:
        if log_error:
            try:
                log_error("OAUTH", "error", message)
            except Exception:  # noqa: BLE001, S110 - logging must never break the flow
                pass

    @app.route("/auth/gal", methods=["GET"])
    def gal_oauth_start():
        cfg = _config()
        if not cfg["enabled"]:
            return _error_page("Вход через GAL", "Вход через GAL отключён.", 404)
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        target = _safe_next(request.args.get("redirect"))
        query = urlencode(
            {
                "response_type": "code",
                "client_id": cfg["client_id"],
                "redirect_uri": _redirect_uri(),
                "state": state,
                "scope": LOGIN_SCOPE,
                "code_challenge": _pkce_challenge(verifier),
                "code_challenge_method": "S256",
            }
        )
        response = redirect(f"{cfg['authorize_url']}?{query}", code=302)
        response.set_cookie(STATE_COOKIE, state, **_cookie_kwargs(COOKIE_MAX_AGE))
        response.set_cookie(VERIFIER_COOKIE, verifier, **_cookie_kwargs(COOKIE_MAX_AGE))
        response.set_cookie(NEXT_COOKIE, target, **_cookie_kwargs(COOKIE_MAX_AGE))
        return response

    @app.route(CALLBACK_PATH, methods=["GET"])
    def gal_oauth_callback():
        cfg = _config()
        if not cfg["enabled"]:
            return _error_page("Вход через GAL", "Вход через GAL отключён.", 404)
        if request.args.get("error"):
            return _error_page(
                "Вход через GAL",
                f"GAL отклонил вход: {request.args.get('error')}",
                400,
            )
        code = (request.args.get("code") or "").strip()
        state = (request.args.get("state") or "").strip()
        expected_state = request.cookies.get(STATE_COOKIE) or ""
        verifier = request.cookies.get(VERIFIER_COOKIE) or ""
        if (
            not code
            or not state
            or not expected_state
            or not hmac.compare_digest(state, expected_state)
        ):
            return _error_page(
                "Вход через GAL", "Неверный state OAuth. Попробуйте войти ещё раз."
            )
        if not verifier:
            return _error_page(
                "Вход через GAL", "Сессия входа через GAL истекла. Попробуйте ещё раз."
            )
        try:
            token_response = requests.post(
                cfg["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": cfg["client_id"],
                    "redirect_uri": _redirect_uri(),
                    "code": code,
                    "code_verifier": verifier,
                },
                timeout=10,
            )
            token_response.raise_for_status()
            access_token = (token_response.json() or {}).get("access_token")
            if not access_token:
                raise ValueError("GAL не выдал access token")
            user_response = requests.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            user_response.raise_for_status()
            profile = user_response.json() or {}
        except (requests.RequestException, ValueError) as exc:
            _log(f"GAL profile error: {exc}")
            return _error_page(
                "Вход через GAL",
                "Не удалось получить профиль GAL. Попробуйте ещё раз.",
                502,
            )

        subject = str(profile.get("sub") or "").strip()
        username = str(
            profile.get("preferred_username") or profile.get("login") or ""
        ).strip()
        display_name = str(
            profile.get("display_name") or profile.get("name") or username
        ).strip()[:100]
        if not subject:
            return _error_page("Вход через GAL", "GAL не вернул идентификатор профиля.")

        try:
            engine = get_db_engine()
            if ensure_columns:
                ensure_columns(engine)
            _ensure_gal_columns(engine)
            created = False
            with engine.begin() as conn:
                row, created = _create_or_get_user(
                    conn,
                    subject=subject,
                    username=username,
                    display_name=display_name or username,
                    hash_password=hash_password,
                )
            user_id = int(row["id"])
            login = row["login"]
        except Exception as exc:
            _log(f"GAL account error: {exc}")
            return _error_page(
                "Вход через GAL",
                "Не удалось создать аккаунт LTHub. Попробуйте ещё раз.",
                500,
            )

        if created and award_coins:
            try:
                award_coins(user_id, 100, "Бонус за регистрацию")
            except Exception as exc:
                _log(f"GAL bonus coins error: {exc}")

        token = create_session(user_id)
        if not token:
            return _error_page("Вход через GAL", "Не удалось создать сессию.", 500)

        target = _safe_next(request.cookies.get(NEXT_COOKIE))
        response = redirect(DONE_PATH + "?redirect=" + quote(target, safe=""), code=302)
        payload = json.dumps({"token": token, "user_id": user_id, "login": login})
        response.set_cookie(
            TOKEN_COOKIE, payload, **_cookie_kwargs(TOKEN_COOKIE_MAX_AGE)
        )
        _clear_flow_cookies(response)
        return response

    @app.route(DONE_PATH, methods=["GET"])
    def gal_oauth_done():
        return _done_page(_safe_next(request.args.get("redirect")))

    @app.route(SESSION_PATH, methods=["GET"])
    def gal_oauth_session():
        raw = request.cookies.get(TOKEN_COOKIE)
        if not raw:
            return jsonify({"error": "not_found"}), 404
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict) or not payload.get("token"):
            return jsonify({"error": "not_found"}), 404
        response = jsonify(payload)
        response.headers["Cache-Control"] = "no-store"
        response.delete_cookie(TOKEN_COOKIE, path="/")
        return response

    return app
