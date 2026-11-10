"""Tests for the LTHub GAL OAuth client (registration/login via GAL)."""

from __future__ import annotations

import os
import tempfile
from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask
from sqlalchemy import create_engine, text

import core.gal_oauth as gal_oauth


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


@pytest.fixture()
def gal_app(monkeypatch):
    db_path = os.path.join(tempfile.mkdtemp(), "gal.db")
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
                    gal_subject VARCHAR(64),
                    gal_username VARCHAR(64)
                )
                """
            )
        )

    monkeypatch.setenv("GAL_OAUTH_ENABLED", "true")
    monkeypatch.setenv("GAL_OAUTH_CLIENT_ID", "lthub")
    monkeypatch.setenv("GAL_OAUTH_AUTHORIZE_URL", "https://gal.test/oauth/authorize")
    monkeypatch.setenv("GAL_OAUTH_TOKEN_URL", "https://gal.test/oauth/token")
    monkeypatch.setenv("GAL_OAUTH_USERINFO_URL", "https://gal.test/oauth/userinfo")
    monkeypatch.setenv(
        "GAL_OAUTH_REDIRECT_URI", "https://lthub.test/api/auth/gal/callback"
    )

    awarded: list[tuple[int, int, str]] = []
    app = Flask(__name__)
    gal_oauth.register_gal_oauth(
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
    response = client.get("/auth/gal?redirect=" + redirect, follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("https://gal.test/oauth/authorize?")
    query = parse_qs(urlparse(location).query)
    return {
        "state": query["state"][0],
        "challenge": query["code_challenge"][0],
        "redirect_uri": query["redirect_uri"][0],
        "verifier": client.get_cookie(gal_oauth.VERIFIER_COOKIE).value,
    }


def _profile(
    monkeypatch, *, sub: str = "gal-1", username: str = "Shadow.Raven"
) -> None:
    monkeypatch.setattr(
        gal_oauth.requests,
        "post",
        lambda *_a, **_k: _Response({"access_token": "gal-access"}),
    )
    monkeypatch.setattr(
        gal_oauth.requests,
        "get",
        lambda *_a, **_k: _Response(
            {
                "sub": sub,
                "preferred_username": username,
                "name": "Shadow Raven",
            }
        ),
    )


def test_start_redirects_with_pkce_and_cookies(gal_app) -> None:
    app, _engine, _awarded = gal_app
    client = app.test_client()
    flow = _start(client, "/account")
    assert flow["redirect_uri"] == "https://lthub.test/api/auth/gal/callback"
    assert len(flow["challenge"]) >= 43
    assert len(flow["verifier"]) >= 43
    assert client.get_cookie(gal_oauth.STATE_COOKIE).value == flow["state"]
    assert client.get_cookie(gal_oauth.NEXT_COOKIE).value == "/account"


def test_callback_rejects_wrong_state(gal_app) -> None:
    app, _engine, _awarded = gal_app
    client = app.test_client()
    _start(client)
    response = client.get(
        "/api/auth/gal/callback?code=abc&state=wrong", follow_redirects=False
    )
    assert response.status_code == 400


def test_callback_creates_account_and_imports_profile(gal_app, monkeypatch) -> None:
    app, engine, awarded = gal_app
    client = app.test_client()
    flow = _start(client, "/account")
    _profile(monkeypatch)

    response = client.get(
        f"/api/auth/gal/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/auth/gal/done?redirect=%2Faccount"

    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM web_users")).mappings().one()
    assert row["login"] == "shadow_raven"
    assert row["display_name"] == "Shadow Raven"
    assert row["gal_subject"] == "gal-1"
    assert row["gal_username"] == "Shadow.Raven"
    assert row["created_via"] == "gal_oauth"
    assert row["password_hash"] == "pbkdf2-hash"
    assert awarded == [(row["id"], 100, "Бонус за регистрацию")]

    session_response = client.get("/api/auth/gal/session")
    assert session_response.status_code == 200
    payload = session_response.get_json()
    assert payload["token"] == f"session-{row['id']}"
    assert payload["user_id"] == row["id"]
    assert payload["login"] == "shadow_raven"
    assert client.get("/api/auth/gal/session").status_code == 404


def test_repeat_login_reuses_linked_account(gal_app, monkeypatch) -> None:
    app, engine, awarded = gal_app
    client = app.test_client()
    flow = _start(client)
    _profile(monkeypatch)
    first = client.get(
        f"/api/auth/gal/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    assert first.status_code == 302

    flow = _start(client)
    second = client.get(
        f"/api/auth/gal/callback?code=def&state={flow['state']}",
        follow_redirects=False,
    )
    assert second.status_code == 302
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM web_users")).scalar()
    assert count == 1
    assert len(awarded) == 1


def test_occupied_login_gets_suffix(gal_app, monkeypatch) -> None:
    app, engine, _awarded = gal_app
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO web_users (login, password_hash, display_name) "
                "VALUES ('alice', 'hash', 'Alice')"
            )
        )
    client = app.test_client()
    flow = _start(client)
    _profile(monkeypatch, sub="gal-2", username="Alice")
    response = client.get(
        f"/api/auth/gal/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    with engine.connect() as conn:
        logins = [row[0] for row in conn.execute(text("SELECT login FROM web_users"))]
    assert "alice" in logins
    assert "alice_2" in logins


def test_short_username_falls_back_to_subject(gal_app, monkeypatch) -> None:
    app, engine, _awarded = gal_app
    client = app.test_client()
    flow = _start(client)
    _profile(monkeypatch, sub="gal-3", username="ab")
    client.get(
        f"/api/auth/gal/callback?code=abc&state={flow['state']}",
        follow_redirects=False,
    )
    with engine.connect() as conn:
        login = conn.execute(text("SELECT login FROM web_users")).scalar()
    assert login.startswith("gal_")
    assert len(login) == 12


def test_done_page_renders_local_redirect(gal_app) -> None:
    app, _engine, _awarded = gal_app
    client = app.test_client()
    response = client.get("/auth/gal/done?redirect=%2Faccount")
    assert response.status_code == 200
    assert '"/account"' in response.text
    evil = client.get("/auth/gal/done?redirect=https%3A%2F%2Fevil.test%2F")
    assert '"https://evil.test/"' not in evil.text
