"""Tests for the personal AI key: /api/account/ai-key + priority in _ai_chat."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

import api.index as idx
from api.index import app

_USER_KEY = "sk-or-v1-testkey-0123456789abcdef"


def _make_engine(with_ai_columns: bool = True):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _now_fn(dbapi_conn, _record):
        def now_impl():
            return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

        dbapi_conn.create_function("NOW", 0, now_impl)

    ai_cols = (
        """
        ai_provider VARCHAR(32),
        ai_api_key VARCHAR(255),
        ai_model VARCHAR(128),
    """
        if with_ai_columns
        else ""
    )
    ddl = f"""
    CREATE TABLE IF NOT EXISTS web_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login VARCHAR(64) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        display_name VARCHAR(100),
        gd_nickname VARCHAR(64),
        telegram_id BIGINT,
        lichess_nickname VARCHAR(64),
        email VARCHAR(255) UNIQUE,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        {ai_cols}
        created_via VARCHAR(32)
    );
    CREATE TABLE IF NOT EXISTS web_sessions (
        token VARCHAR(64) PRIMARY KEY,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS rate_limits (
        key TEXT NOT NULL, ts DOUBLE PRECISION NOT NULL
    );
    """
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    return engine


def _auth_headers(token: str) -> dict:
    return {"X-Auth-Token": token}


def _register(client, login="keyuser"):
    r = client.post(
        "/api/auth/register",
        json={"login": login, "password": "secret123", "email": f"{login}@t.local"},
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["token"]


def _save_key(
    client, token, provider="openrouter", api_key=_USER_KEY, model="test/model"
):
    return client.post(
        "/api/account/ai-key",
        json={"provider": provider, "api_key": api_key, "model": model},
        headers=_auth_headers(token),
    )


def _resp(status_code: int, content: str = "") -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.text = "mock-body"
    r.json.return_value = {"choices": [{"message": {"content": content}}]}
    return r


@pytest.fixture
def ai_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "server_gem_key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setitem(idx._groq_active_model, "name", None)


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_ai_key_requires_auth(_rate, _ai_rate, mock_engine):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    assert client.get("/api/account/ai-key").status_code == 401
    assert client.post("/api/account/ai-key", json={}).status_code == 401
    assert client.delete("/api/account/ai-key").status_code == 401


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_ai_key_save_get_delete(_rate, _ai_rate, mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    token = _register(client)

    assert client.get(
        "/api/account/ai-key", headers=_auth_headers(token)
    ).get_json() == {"has_key": False}

    r = _save_key(client, token)
    assert r.status_code == 200, r.get_json()

    # Ключ лежит в БД в открытом виде
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT ai_provider, ai_api_key, ai_model FROM web_users")
        ).first()
    assert row == ("openrouter", _USER_KEY, "test/model")

    d = client.get("/api/account/ai-key", headers=_auth_headers(token)).get_json()
    assert d["has_key"] is True
    assert d["provider"] == "openrouter"
    assert d["model"] == "test/model"
    assert d["key_preview"].endswith(_USER_KEY[-4:])
    # Полный ключ наружу не отдаём
    assert _USER_KEY not in str(d)

    r = client.delete("/api/account/ai-key", headers=_auth_headers(token))
    assert r.status_code == 200
    assert client.get(
        "/api/account/ai-key", headers=_auth_headers(token)
    ).get_json() == {"has_key": False}
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT ai_provider, ai_api_key, ai_model FROM web_users")
        ).first()
    assert row == (None, None, None)


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_ai_key_validation(_rate, _ai_rate, mock_engine):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    token = _register(client)
    h = _auth_headers(token)
    assert _save_key(client, token, provider="unknown").status_code == 400
    assert _save_key(client, token, api_key="").status_code == 400
    assert _save_key(client, token, api_key="k" * 256).status_code == 400
    assert _save_key(client, token, model="m" * 129).status_code == 400
    # модель необязательна
    assert _save_key(client, token, model="").status_code == 200
    assert client.get("/api/account/ai-key", headers=h).get_json()["model"] == ""


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_user_key_used_first(_rate, _ai_rate, mock_engine, ai_env):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    token = _register(client)
    assert _save_key(client, token).status_code == 200

    ok = _resp(200, "user key answer")
    with patch("api.index.requests.post", return_value=ok) as m:
        with app.test_request_context("/", headers=_auth_headers(token)):
            out = idx._ai_chat({"messages": [{"role": "user", "content": "hi"}]})
    assert out is ok
    assert m.call_count == 1
    assert "openrouter.ai" in m.call_args[0][0]
    assert m.call_args[1]["headers"]["Authorization"] == f"Bearer {_USER_KEY}"
    assert m.call_args[1]["json"]["model"] == "test/model"


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_user_key_failure_falls_back_to_server(_rate, _ai_rate, mock_engine, ai_env):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    token = _register(client)
    assert _save_key(client, token).status_code == 200

    bad = _resp(401)
    gem = _resp(200, "server answer")
    with patch("api.index.requests.post", side_effect=[bad, gem]) as m:
        with app.test_request_context("/", headers=_auth_headers(token)):
            out = idx._ai_chat({"messages": [{"role": "user", "content": "hi"}]})
    assert out is gem
    assert m.call_count == 2
    assert "openrouter.ai" in m.call_args_list[0][0][0]
    assert "generativelanguage.googleapis.com" in m.call_args_list[1][0][0]
    assert m.call_args_list[1][1]["headers"]["Authorization"] == "Bearer server_gem_key"


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_user_key_empty_reply_falls_back(_rate, _ai_rate, mock_engine, ai_env):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    token = _register(client)
    assert _save_key(client, token).status_code == 200

    empty = _resp(200, "")
    gem = _resp(200, "server answer")
    with patch("api.index.requests.post", side_effect=[empty, gem]) as m:
        with app.test_request_context("/", headers=_auth_headers(token)):
            out = idx._ai_chat({"messages": [{"role": "user", "content": "hi"}]})
    assert out is gem
    assert m.call_count == 2


@patch("api.index.get_db_engine")
@patch("api.index._check_ai_rate", return_value=False)
@patch("api.index._check_db_rate", return_value=False)
def test_no_user_key_server_chain_first(_rate, _ai_rate, mock_engine, ai_env):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    token = _register(client)

    gem = _resp(200, "server answer")
    with patch("api.index.requests.post", return_value=gem) as m:
        with app.test_request_context("/", headers=_auth_headers(token)):
            out = idx._ai_chat({"messages": [{"role": "user", "content": "hi"}]})
    assert out is gem
    assert m.call_count == 1
    assert "generativelanguage.googleapis.com" in m.call_args[0][0]


def test_ai_chat_outside_request_context_ignores_user_key(ai_env):
    """Без Flask-контекста (бот/скрипты) серверная цепочка не меняется."""
    gem = _resp(200, "server answer")
    with patch("api.index.requests.post", return_value=gem) as m:
        out = idx._ai_chat({"messages": [{"role": "user", "content": "hi"}]})
    assert out is gem
    assert "generativelanguage.googleapis.com" in m.call_args[0][0]


def test_ensure_web_user_columns_adds_ai_columns():
    engine = _make_engine(with_ai_columns=False)
    idx._ensure_web_user_columns(engine)
    with engine.connect() as conn:
        cols = {
            str(r[1]).lower()
            for r in conn.execute(text("PRAGMA table_info(web_users)")).all()
        }
    assert {"ai_provider", "ai_api_key", "ai_model"} <= cols
    # повторный запуск идемпотентен
    idx._ensure_web_user_columns(engine)


@patch("api.index.get_db_engine")
def test_account_page_has_ai_key_ui(mock_engine):
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    r = client.get("/account")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Мой AI-ключ" in html
    assert "/api/account/ai-key" in html
    assert "saveAiKey" in html
