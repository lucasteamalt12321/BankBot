"""Tests for the Textbook Tracker module."""

from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from api.index import app


def _make_engine():
    """In-memory SQLite engine with textbooks + auth tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _now_fn(dbapi_conn, _):
        def now_impl():
            return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        dbapi_conn.create_function("NOW", 0, now_impl)

    ddl = """
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_sessions (
        token VARCHAR(64) PRIMARY KEY,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS textbooks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id BIGINT NOT NULL,
        subject VARCHAR(100) NOT NULL,
        title VARCHAR(200) NOT NULL,
        location VARCHAR(20) NOT NULL DEFAULT 'home',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    with engine.connect() as conn:
        for stmt in ddl.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
    return engine


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_user(client):
    r = client.post("/api/auth/register", json={"login": "tb_user", "password": "pass1234", "email": "tb@test.local"})
    return r.get_json().get("token")


@patch("api.index.get_db_engine")
def test_create_and_list(mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    token = _create_user(client)

    r = client.post("/api/textbooks", json={
        "subject": "Математика", "title": "Алгебра 9 класс", "location": "home"
    }, headers=_auth_headers(token))
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "id" in data

    r = client.get("/api/textbooks", headers=_auth_headers(token))
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert len(items) == 1
    assert items[0]["subject"] == "Математика"
    assert items[0]["title"] == "Алгебра 9 класс"
    assert items[0]["location"] == "home"


@patch("api.index.get_db_engine")
def test_move_book(mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    token = _create_user(client)

    r = client.post("/api/textbooks", json={
        "subject": "Физика", "title": "Мякишев 10 класс"
    }, headers=_auth_headers(token))
    book_id = r.get_json()["id"]

    r = client.put(f"/api/textbooks/{book_id}/move", json={"location": "school"},
                    headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    r = client.get("/api/textbooks", headers=_auth_headers(token))
    items = r.get_json()["items"]
    assert items[0]["location"] == "school"


@patch("api.index.get_db_engine")
def test_delete_book(mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    token = _create_user(client)

    r = client.post("/api/textbooks", json={
        "subject": "История", "title": "История России 9 класс"
    }, headers=_auth_headers(token))
    book_id = r.get_json()["id"]

    r = client.delete(f"/api/textbooks/{book_id}", headers=_auth_headers(token))
    assert r.status_code == 200

    r = client.get("/api/textbooks", headers=_auth_headers(token))
    assert len(r.get_json()["items"]) == 0


@patch("api.index.get_db_engine")
def test_auth_required(mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()

    r = client.get("/api/textbooks")
    assert r.status_code == 401

    r = client.post("/api/textbooks", json={"subject": "Математика", "title": "Test"})
    assert r.status_code == 401


@patch("api.index.get_db_engine")
def test_validation(mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    token = _create_user(client)

    r = client.post("/api/textbooks", json={"subject": "Несуществующий", "title": "Test"},
                    headers=_auth_headers(token))
    assert r.status_code == 400

    r = client.post("/api/textbooks", json={"subject": "Математика", "title": ""},
                    headers=_auth_headers(token))
    assert r.status_code == 400

    r = client.post("/api/textbooks", json={"subject": "Математика", "title": "X", "location": "mars"},
                    headers=_auth_headers(token))
    assert r.status_code == 400

    r = client.put("/api/textbooks/1/move", json={"location": "mars"},
                    headers=_auth_headers(token))
    assert r.status_code == 400


@patch("api.index.get_db_engine")
def test_multiple_books_same_subject(mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    token = _create_user(client)

    client.post("/api/textbooks", json={"subject": "Математика", "title": "Алгебра 9"},
                headers=_auth_headers(token))
    client.post("/api/textbooks", json={"subject": "Математика", "title": "Геометрия 9"},
                headers=_auth_headers(token))

    r = client.get("/api/textbooks", headers=_auth_headers(token))
    items = r.get_json()["items"]
    assert len(items) == 2
    titles = {i["title"] for i in items}
    assert "Алгебра 9" in titles
    assert "Геометрия 9" in titles


@patch("api.index.get_db_engine")
def test_move_nonexistent(mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    token = _create_user(client)

    r = client.put("/api/textbooks/9999/move", json={"location": "school"},
                    headers=_auth_headers(token))
    assert r.status_code == 404


@patch("api.index.get_db_engine")
def test_delete_nonexistent(mock_engine):
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()
    token = _create_user(client)

    r = client.delete("/api/textbooks/9999", headers=_auth_headers(token))
    assert r.status_code == 404
