"""Sign in / sign up to LTHub through Google (OAuth 2.0 code + PKCE).

The authorization code is exchanged server-side with the client secret, so the
profile comes from Google's userinfo endpoint over TLS (no JWT verification
library needed). The callback creates a LTHub account from the Google profile
or reuses the account linked by ``web_users.google_subject``.
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

STATE_COOKIE = "google_oauth_state"
VERIFIER_COOKIE = "google_oauth_verifier"
NEXT_COOKIE = "google_oauth_next"
TOKEN_COOKIE = "google_oauth_token"
COOKIE_MAX_AGE = 600
TOKEN_COOKIE_MAX_AGE = 120
CALLBACK_PATH = "/api/auth/google/callback"
DONE_PATH = "/auth/google/done"
SESSION_PATH = "/api/auth/google/session"
LOGIN_SCOPE = "openid email profile"


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
        "enabled": _flag("GOOGLE_OAUTH_ENABLED"),
        "client_id": (os.getenv("GOOGLE_CLIENT_ID") or "").strip(),
        "client_secret": (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip(),
        "authorize_url": (
            os.getenv("GOOGLE_OAUTH_AUTHORIZE_URL")
            or "https://accounts.google.com/o/oauth2/v2/auth"
        ).strip(),
        "token_url": (
            os.getenv("GOOGLE_OAUTH_TOKEN_URL") or "https://oauth2.googleapis.com/token"
        ).strip(),
        "userinfo_url": (
            os.getenv("GOOGLE_OAUTH_USERINFO_URL")
            or "https://openidconnect.googleapis.com/v1/userinfo"
        ).strip(),
    }


def google_oauth_available() -> bool:
    cfg = _config()
    return bool(cfg["enabled"] and cfg["client_id"] and cfg["client_secret"])


def _redirect_uri() -> str:
    configured = (os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or "").strip()
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
    if target.startswith(("/auth/google", "/api/auth/google")):
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
<title>Вход через Google — LTHub</title>
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
<h1>Вход через Google</h1>
<p id="status">Завершаем вход…</p>
</main>
<script>
const TARGET = {target};
fetch("/api/auth/google/session", {{credentials: "same-origin", cache: "no-store"}})
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
    digest = hashlib.sha256((subject or "google").encode("utf-8")).hexdigest()[:8]
    return f"google_{digest}"


def _login_candidates(base: str) -> list[str]:
    candidates = [base]
    stem = base[:60].rstrip("_") or "google"
    candidates.extend(f"{stem}_{index}" for index in range(2, 10))
    candidates.append(f"{stem[:48]}_{secrets.token_hex(3)}")
    return candidates


def _find_linked_user(conn, subject: str):
    return (
        conn.execute(
            text(
                "SELECT id, login, display_name FROM web_users "
                "WHERE google_subject = :subject"
            ),
            {"subject": subject},
        )
        .mappings()
        .first()
    )


def _create_or_get_user(
    conn, *, subject: str, login_base: str, display_name: str, email: str, hash_password
):
    linked = _find_linked_user(conn, subject)
    if linked:
        return linked, False

    login = sanitize_login(login_base, subject)
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
                             google_subject, google_email)
                        VALUES (:login, :password_hash, :display_name, 'google_oauth',
                                :subject, :email)
                        RETURNING id, login, display_name
                        """
                        ),
                        {
                            "login": candidate,
                            "password_hash": hash_password(secrets.token_urlsafe(32)),
                            "display_name": display_name,
                            "subject": subject,
                            "email": email[:255],
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


def _ensure_google_columns(engine) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_web_users_google_subject "
                    "ON web_users (google_subject)"
                )
            )
    except Exception as exc:  # noqa: BLE001 - optional index on legacy schemas
        logger.debug("Google OAuth index creation skipped: %s", exc)


def register_google_oauth(
    app,
    *,
    get_db_engine,
    create_session,
    hash_password,
    ensure_columns=None,
    award_coins=None,
    log_error=None,
):
    """Register Google OAuth client routes on the Flask app."""

    def _log(message: str) -> None:
        if log_error:
            try:
                log_error("GOOGLE_OAUTH", "error", message)
            except Exception:  # noqa: BLE001, S110 - logging must never break the flow
                pass

    @app.route("/auth/google", methods=["GET"])
    def google_oauth_start():
        if not google_oauth_available():
            return _error_page(
                "Вход через Google",
                "Вход через Google не настроен. Войдите по логину и паролю.",
                404,
            )
        cfg = _config()
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
                "prompt": "select_account",
            }
        )
        response = redirect(f"{cfg['authorize_url']}?{query}", code=302)
        response.set_cookie(STATE_COOKIE, state, **_cookie_kwargs(COOKIE_MAX_AGE))
        response.set_cookie(VERIFIER_COOKIE, verifier, **_cookie_kwargs(COOKIE_MAX_AGE))
        response.set_cookie(NEXT_COOKIE, target, **_cookie_kwargs(COOKIE_MAX_AGE))
        return response

    @app.route(CALLBACK_PATH, methods=["GET"])
    def google_oauth_callback():
        if not google_oauth_available():
            return _error_page(
                "Вход через Google",
                "Вход через Google не настроен. Войдите по логину и паролю.",
                404,
            )
        cfg = _config()
        if request.args.get("error"):
            return _error_page(
                "Вход через Google",
                f"Google отклонил вход: {request.args.get('error')}",
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
                "Вход через Google",
                "Неверный state OAuth. Попробуйте войти ещё раз.",
            )
        if not verifier:
            return _error_page(
                "Вход через Google",
                "Сессия входа через Google истекла. Попробуйте ещё раз.",
            )
        try:
            token_response = requests.post(
                cfg["token_url"],
                data={
                    "grant_type": "authorization_code",
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                    "redirect_uri": _redirect_uri(),
                    "code": code,
                    "code_verifier": verifier,
                },
                timeout=10,
            )
            token_response.raise_for_status()
            access_token = (token_response.json() or {}).get("access_token")
            if not access_token:
                raise ValueError("Google не выдал access token")
            user_response = requests.get(
                cfg["userinfo_url"],
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            user_response.raise_for_status()
            profile = user_response.json() or {}
        except (requests.RequestException, ValueError) as exc:
            _log(f"Google profile error: {exc}")
            return _error_page(
                "Вход через Google",
                "Не удалось получить профиль Google. Попробуйте ещё раз.",
                502,
            )

        subject = str(profile.get("sub") or "").strip()
        email = str(profile.get("email") or "").strip()
        display_name = str(
            profile.get("name") or profile.get("given_name") or ""
        ).strip()[:100]
        if not subject:
            return _error_page(
                "Вход через Google", "Google не вернул идентификатор профиля."
            )
        login_base = email.split("@")[0] if email else display_name
        if not display_name:
            display_name = login_base

        try:
            engine = get_db_engine()
            if ensure_columns:
                ensure_columns(engine)
            _ensure_google_columns(engine)
            with engine.begin() as conn:
                row, created = _create_or_get_user(
                    conn,
                    subject=subject,
                    login_base=login_base,
                    display_name=display_name,
                    email=email,
                    hash_password=hash_password,
                )
            user_id = int(row["id"])
            login = row["login"]
        except Exception as exc:
            _log(f"Google account error: {exc}")
            return _error_page(
                "Вход через Google",
                "Не удалось создать аккаунт LTHub. Попробуйте ещё раз.",
                500,
            )

        if created and award_coins:
            try:
                award_coins(user_id, 100, "Бонус за регистрацию")
            except Exception as exc:
                _log(f"Google bonus coins error: {exc}")

        token = create_session(user_id)
        if not token:
            return _error_page("Вход через Google", "Не удалось создать сессию.", 500)

        target = _safe_next(request.cookies.get(NEXT_COOKIE))
        response = redirect(DONE_PATH + "?redirect=" + quote(target, safe=""), code=302)
        payload = json.dumps({"token": token, "user_id": user_id, "login": login})
        response.set_cookie(
            TOKEN_COOKIE, payload, **_cookie_kwargs(TOKEN_COOKIE_MAX_AGE)
        )
        _clear_flow_cookies(response)
        return response

    @app.route(DONE_PATH, methods=["GET"])
    def google_oauth_done():
        return _done_page(_safe_next(request.args.get("redirect")))

    @app.route(SESSION_PATH, methods=["GET"])
    def google_oauth_session():
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
