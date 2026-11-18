"""Tests for the LTHub Google OAuth client (registration/login via Google)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask
from sqlalchemy import create_engine, text

import core.google_oauth as google_oauth


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.fixture()
def google_app(monkeypatch):
    db_path = os.path.join(tempfile.mkdtemp(), "google.db")
    engine = create_engine("sqlite:///" + db_path.replace("\\", "/"))
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE web_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    login VARCHAR(64) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    display_name VARCHAR(100),
                    email VARCHAR(255) UNIQUE,
                    created_via VARCHAR(32),
                    google_subject VARCHAR(64),
                    google_email VARCHAR(255)
                )
                """
            )
        )

    monkeypatch.setenv("GOOGLE_OAUTH_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_AUTHORIZE_URL", "https://accounts.google.test/o/oauth2/v2/auth"
    )
    monkeypatch.setenv("GOOGLE_OAUTH_TOKEN_URL", "https://oauth2.google.test/token")
    monkeypatch.setenv(
        "GOOGLE_OAUTH_USERINFO_URL", "https://openidconnect.google.test/v1/userinfo"
    )
    monkeypatch.setenv(
        "GOOGLE_OAUTH_REDIRECT_URI", "https://lthub.test/api/auth/google/callback"
    )

    awarded: list[tuple[int, int, str]] = []
    app = Flask(__name__)
    google_oauth.register_google_oauth(
        app,
        get_db_engine=lambda: engine,
        create_session=lambda user_id: f"session-{user_id}",
        hash_password=lambda _password: "pbkdf2-hash",
        award_coins=lambda user_id, amount, description: awarded.append(
            (user_id, amount, description)
        ),
    )
    app.config["TESTING"] = True
    yield app, engine, awarded
    engine.dispose()


def _start(client, redirect: str = "/") -> dict[str, str]:
    response = client.get("/auth/google?redirect=" + redirect, follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("https://accounts.google.test/o/oauth2/v2/auth?")
    query = parse_qs(urlparse(location).query)
    return {
        "state": query["state"][0],
        "challenge": query["code_challenge"][0],
        "redirect_uri": query["redirect_uri"][0],
        "scope": query["scope"][0],
        "verifier": client.get_cookie(google_oauth.VERIFIER_COOKIE).value,
    }


def _profile(
    monkeypatch,
    *,
    sub: str = "google-1",
    email: str = "Shadow.Raven@gmail.com",
    name: str = "Shadow Raven",
) -> None:
    monkeypatch.setattr(
        google_oauth.requests,
        "post",
        lambda *_a, **_k: _Response({"access_token": "google-access"}),
    )
    monkeypatch.setattr(
        google_oauth.requests,
        "get",
        lambda *_a, **_k: _Response(
            {"sub": sub, "email": email, "email_verified": True, "name": name}
        ),
    )


def test_start_redirects_with_pkce_and_cookies(google_app) -> None:
    app, _engine, _awarded = google_app
    client = app.test_client()
    flow = _start(client, "/account")
    assert flow["redirect_uri"] == "https://lthub.test/api/auth/google/callback"
    assert flow["scope"] == "openid email profile"
    assert len(flow["challenge"]) >= 43
    assert len(flow["verifier"]) >= 43
    assert client.get_cookie(google_oauth.STATE_COOKIE).value == flow["state"]
    assert client.get_cookie(google_oauth.NEXT_COOKIE).value == "/account"


def test_start_sanitizes_external_redirect(google_app) -> None:
    app, _engine, _awarded = google_app
    client = app.test_client()
    response = client.get(
        "/auth/google?redirect=https%3A%2F%2Fevil.test%2F", follow_redirects=False
    )
    assert response.status_code == 302
    assert client.get_cookie(google_oauth.NEXT_COOKIE).value == "/"


def test_unconfigured_returns_404(google_app, monkeypatch) -> None:
    app, _engine, _awarded = google_app
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    client = app.test_client()
    assert client.get("/auth/google").status_code == 404
    assert client.get("/api/auth/google/callback?code=a&state=b").status_code == 404


def test_disabled_flag_returns_404(google_app, monkeypatch) -> None:
    app, _engine, _awarded = google_app
    monkeypatch.setenv("GOOGLE_OAUTH_ENABLED", "false")
    client = app.test_client()
    assert client.get("/auth/google").status_code == 404


def test_callback_rejects_wrong_state(google_app) -> None:
    app, _engine, _awarded = google_app
    client = app.test_client()
    _start(client)
    response = client.get(
        "/api/auth/google/callback?code=abc&state=wrong", follow_redirects=False
    )
    assert response.status_code == 400


def test_callback_rejects_google_error(google_app) -> None:
    app, _engine, _awarded = google_app
    client = app.test_client()
    _start(client)
    response = client.get(
        "/api/auth/google/callback?error=access_denied", follow_redirects=False
    )
    assert response.status_code == 400


def test_callback_creates_account_and_imports_profile(google_app, monkeypatch) -> None:
    app, engine, awarded = google_app
    client = app.test_client()
    flow = _start(client, "/account")
    _profile(monkeypatch)

    response = client.get(
        f"/api/auth/google/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/google/done?redirect=%2Faccount"

    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM web_users")).mappings().one()
    assert row["login"] == "shadow_raven"
    assert row["display_name"] == "Shadow Raven"
    assert row["google_subject"] == "google-1"
    assert row["google_email"] == "Shadow.Raven@gmail.com"
    assert row["created_via"] == "google_oauth"
    assert row["password_hash"] == "pbkdf2-hash"
    assert row["email"] is None
    assert awarded == [(row["id"], 100, "Бонус за регистрацию")]

    session_response = client.get("/api/auth/google/session")
    assert session_response.status_code == 200
    payload = session_response.get_json()
    assert payload["token"] == f"session-{row['id']}"
    assert payload["user_id"] == row["id"]
    assert payload["login"] == "shadow_raven"
    assert client.get("/api/auth/google/session").status_code == 404


def test_repeat_login_reuses_linked_account(google_app, monkeypatch) -> None:
    app, engine, awarded = google_app
    client = app.test_client()
    flow = _start(client)
    _profile(monkeypatch)
    first = client.get(
        f"/api/auth/google/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    assert first.status_code == 302

    flow = _start(client)
    second = client.get(
        f"/api/auth/google/callback?code=def&state={flow['state']}",
        follow_redirects=False,
    )
    assert second.status_code == 302
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM web_users")).scalar()
    assert count == 1
    assert len(awarded) == 1


def test_occupied_login_gets_suffix(google_app, monkeypatch) -> None:
    app, engine, _awarded = google_app
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO web_users (login, password_hash, display_name) "
                "VALUES ('alice', 'hash', 'Alice')"
            )
        )
    client = app.test_client()
    flow = _start(client)
    _profile(monkeypatch, sub="google-2", email="alice@gmail.com", name="Alice")
    response = client.get(
        f"/api/auth/google/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    with engine.connect() as conn:
        logins = [row[0] for row in conn.execute(text("SELECT login FROM web_users"))]
    assert "alice" in logins
    assert "alice_2" in logins


def test_no_email_falls_back_to_name(google_app, monkeypatch) -> None:
    app, engine, _awarded = google_app
    client = app.test_client()
    flow = _start(client)
    _profile(monkeypatch, sub="google-3", email="", name="Some User")
    client.get(
        f"/api/auth/google/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    with engine.connect() as conn:
        row = conn.execute(text("SELECT login, google_email FROM web_users")).one()
    assert row[0] == "some_user"
    assert row[1] == ""


def test_no_name_no_email_falls_back_to_subject(google_app, monkeypatch) -> None:
    app, engine, _awarded = google_app
    client = app.test_client()
    flow = _start(client)
    _profile(monkeypatch, sub="google-4", email="", name="")
    client.get(
        f"/api/auth/google/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    with engine.connect() as conn:
        login = conn.execute(text("SELECT login FROM web_users")).scalar()
    assert login.startswith("google_")
    assert len(login) == 15


def test_missing_sub_rejected(google_app, monkeypatch) -> None:
    app, engine, _awarded = google_app
    client = app.test_client()
    flow = _start(client)
    _profile(monkeypatch, sub="")
    response = client.get(
        f"/api/auth/google/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    assert response.status_code == 400
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM web_users")).scalar()
    assert count == 0


def test_token_exchange_failure_returns_502(google_app, monkeypatch) -> None:
    app, _engine, _awarded = google_app
    client = app.test_client()
    flow = _start(client)

    def _boom(*_a, **_k):
        raise google_oauth.requests.RequestException("network down")

    monkeypatch.setattr(google_oauth.requests, "post", _boom)
    response = client.get(
        f"/api/auth/google/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    assert response.status_code == 502


def test_done_page_renders_local_redirect(google_app) -> None:
    app, _engine, _awarded = google_app
    client = app.test_client()
    response = client.get("/auth/google/done?redirect=%2Faccount")
    assert response.status_code == 200
    assert '"/account"' in response.text
    evil = client.get("/auth/google/done?redirect=https%3A%2F%2Fevil.test%2F")
    assert '"https://evil.test/"' not in evil.text


def test_session_without_cookie_404(google_app) -> None:
    app, _engine, _awarded = google_app
    client = app.test_client()
    assert client.get("/api/auth/google/session").status_code == 404


# === Интеграция со страницами /login и /register реального приложения ===


def _portal_client(monkeypatch, *, configured: bool):
    from api.index import app

    if configured:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "x.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
    else:
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setenv("GOOGLE_OAUTH_ENABLED", "true")
    return app.test_client()


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_pages_show_google_button_when_configured(monkeypatch, path) -> None:
    client = _portal_client(monkeypatch, configured=True)
    response = client.get(path)
    assert response.status_code == 200
    assert "btn-google" in response.text
    assert "Войти через Google" in response.text or "через Google" in response.text
    assert "var GOOGLE_OAUTH_ON = true;" in response.text
    assert "__GOOGLE_OAUTH_ON__" not in response.text


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_pages_hide_google_button_when_unconfigured(monkeypatch, path) -> None:
    client = _portal_client(monkeypatch, configured=False)
    response = client.get(path)
    assert response.status_code == 200
    assert "var GOOGLE_OAUTH_ON = false;" in response.text
    assert "__GOOGLE_OAUTH_ON__" not in response.text


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_pages_inline_js_parses(monkeypatch, path) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available")
    client = _portal_client(monkeypatch, configured=True)
    response = client.get(path)
    scripts = re.findall(r"<script>(.*?)</script>", response.text, re.S)
    assert scripts
    for script in scripts:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".js", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(script)
            script_path = handle.name
        try:
            result = subprocess.run(
                [node, "--check", script_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, result.stderr
        finally:
            os.unlink(script_path)
