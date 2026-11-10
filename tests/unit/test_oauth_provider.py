"""Unit tests for the LTHub OAuth provider (authorization code + PKCE)."""

from __future__ import annotations

import json
import os
import tempfile

import pytest
from flask import Flask
from sqlalchemy import create_engine, text

from core.oauth import _pkce_challenge, register_oauth


@pytest.fixture()
def oauth_app():
    db_path = os.path.join(tempfile.mkdtemp(), "oauth.db")
    engine = create_engine("sqlite:///" + db_path.replace("\\", "/"))
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE web_users "
                "(id INTEGER PRIMARY KEY, login TEXT, display_name TEXT)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO web_users (id, login, display_name) "
                "VALUES (7, 'alice', 'Alice')"
            )
        )

    app = Flask(__name__)
    register_oauth(
        app,
        get_db_engine=lambda: engine,
        get_session_user=lambda token: (
            {"id": 7, "login": "alice", "display_name": "Alice"}
            if token == "session-token"
            else None
        ),
        auth_token=lambda: None,
    )
    yield app
    engine.dispose()


def _authorize_params(challenge: str) -> dict:
    return {
        "client_id": "gal",
        "redirect_uri": "https://gal-inky.vercel.app/auth/lthub/callback",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "state-1",
    }


def test_authorize_page_renders(oauth_app) -> None:
    client = oauth_app.test_client()
    verifier = "a" * 64
    query = (
        "/oauth/authorize?response_type=code&client_id=gal"
        "&redirect_uri=https%3A%2F%2Fgal-inky.vercel.app%2Fauth%2Flthub%2Fcallback"
        f"&state=state-1&code_challenge={_pkce_challenge(verifier)}"
        "&code_challenge_method=S256"
    )
    response = client.get(query)
    assert response.status_code == 200
    assert b"Global Achievement List" in response.data


def test_authorize_page_register_intent(oauth_app) -> None:
    client = oauth_app.test_client()
    verifier = "e" * 64
    query = (
        "/oauth/authorize?response_type=code&client_id=gal&intent=register"
        "&redirect_uri=https%3A%2F%2Fgal-inky.vercel.app%2Fauth%2Flthub%2Fcallback"
        f"&state=state-1&code_challenge={_pkce_challenge(verifier)}"
        "&code_challenge_method=S256"
    )
    response = client.get(query)
    assert response.status_code == 200
    assert b'const MODE_PATH = "/register";' in response.data
    assert json.dumps("Зарегистрироваться").encode() in response.data


def test_authorize_page_unknown_intent_falls_back_to_login(oauth_app) -> None:
    client = oauth_app.test_client()
    verifier = "f" * 64
    query = (
        "/oauth/authorize?response_type=code&client_id=gal&intent=hacked"
        "&redirect_uri=https%3A%2F%2Fgal-inky.vercel.app%2Fauth%2Flthub%2Fcallback"
        f"&state=state-1&code_challenge={_pkce_challenge(verifier)}"
        "&code_challenge_method=S256"
    )
    response = client.get(query)
    assert response.status_code == 200
    assert b'const MODE_PATH = "/login";' in response.data


def test_authorize_requires_session(oauth_app) -> None:
    client = oauth_app.test_client()
    response = client.post(
        "/api/oauth/authorize",
        json={"client_id": "gal", **_authorize_params(_pkce_challenge("a" * 64))},
    )
    assert response.status_code == 401


def test_full_code_flow_and_one_time_code(oauth_app) -> None:
    client = oauth_app.test_client()
    verifier = "b" * 64
    params = _authorize_params(_pkce_challenge(verifier))
    response = client.post(
        "/api/oauth/authorize",
        json={"token": "session-token", **params},
    )
    assert response.status_code == 200
    redirect_url = response.get_json()["redirect_url"]
    assert redirect_url.startswith(params["redirect_uri"])
    code = redirect_url.split("code=", 1)[1].split("&", 1)[0]

    token_response = client.post(
        "/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": "gal",
            "redirect_uri": params["redirect_uri"],
            "code": code,
            "code_verifier": verifier,
        },
    )
    assert token_response.status_code == 200
    payload = token_response.get_json()
    assert payload["token_type"] == "Bearer"
    access_token = payload["access_token"]

    info = client.get(
        "/oauth/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert info.status_code == 200
    assert info.get_json()["sub"] == "7"
    assert info.get_json()["login"] == "alice"

    reused = client.post(
        "/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": "gal",
            "redirect_uri": params["redirect_uri"],
            "code": code,
            "code_verifier": verifier,
        },
    )
    assert reused.status_code == 400


def test_wrong_verifier_rejected(oauth_app) -> None:
    client = oauth_app.test_client()
    verifier = "c" * 64
    params = _authorize_params(_pkce_challenge(verifier))
    redirect_url = client.post(
        "/api/oauth/authorize", json={"token": "session-token", **params}
    ).get_json()["redirect_url"]
    code = redirect_url.split("code=", 1)[1].split("&", 1)[0]
    response = client.post(
        "/oauth/token",
        json={
            "grant_type": "authorization_code",
            "client_id": "gal",
            "redirect_uri": params["redirect_uri"],
            "code": code,
            "code_verifier": "d" * 64,
        },
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_code_verifier"
