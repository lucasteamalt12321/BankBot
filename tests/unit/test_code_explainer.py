"""Tests for the Code Explainer module."""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from api.index import app


def _make_engine():
    """In-memory SQLite engine with code + auth tables."""
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
    CREATE TABLE IF NOT EXISTS rate_limits (
        key TEXT NOT NULL,
        ts DOUBLE PRECISION NOT NULL
    );
    CREATE TABLE IF NOT EXISTS code_projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id BIGINT NOT NULL,
        repo_url VARCHAR(500) NOT NULL,
        repo_name VARCHAR(300),
        primary_language VARCHAR(50),
        status VARCHAR(20) NOT NULL DEFAULT 'analyzing',
        file_count INTEGER NOT NULL DEFAULT 0,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS code_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        file_type VARCHAR(10) NOT NULL,
        parent_path TEXT,
        language VARCHAR(50),
        line_count INTEGER NOT NULL DEFAULT 0,
        content TEXT,
        ai_summary TEXT,
        ai_line_comments TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(project_id, file_path)
    );
    CREATE TABLE IF NOT EXISTS code_user_comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        line_start INTEGER,
        line_end INTEGER,
        comment TEXT NOT NULL,
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
    r = client.post("/api/auth/register", json={"login": "code_user", "password": "pass1234", "email": "code@test.local"})
    return r.get_json().get("token")


def _fake_godot_repo(dest):
    """Create a small fake Godot repo in dest."""
    main_dir = os.path.join(dest, "player")
    os.makedirs(main_dir, exist_ok=True)
    with open(os.path.join(dest, "project.godot"), "w", encoding="utf-8") as fh:
        fh.write('config_version=5\n\n[application]\nconfig/name="Fake"\n')
    with open(os.path.join(dest, "player", "player.gd"), "w", encoding="utf-8") as fh:
        fh.write("extends CharacterBody2D\n\n@export var speed = 300\n\nvar health = 100\n\nfunc _physics_process(delta):\n    pass\n")
    with open(os.path.join(dest, "player", "player.tscn"), "w", encoding="utf-8") as fh:
        fh.write('[gd_scene load_steps=2 format=3]\n\n[node name="Player" type="CharacterBody2D"]\n')


_AI_FILE_RESPONSE = json.dumps({
    "files": {
        "player/player.gd": {
            "summary": "Игрок: управление и здоровье.",
            "line_comments": {"1": "Класс игрока", "3": "Скорость движения", "5": "Точка входа"},
        }
    }
})


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_analyze_flow(mock_ai, mock_clone, tmp_path):
    def _fake_clone(url, dest, timeout=30):
        _fake_godot_repo(dest)
        return True

    mock_clone.side_effect = _fake_clone
    mock_ai.return_value = _AI_FILE_RESPONSE

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _create_user(client)

        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/fake"},
                        headers=_auth_headers(token))
        assert r.status_code == 200, r.get_json()
        data = r.get_json()
        assert data["ok"] is True
        pid = data["project_id"]

        # project listed
        r = client.get("/api/code/projects", headers=_auth_headers(token))
        items = r.get_json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == pid
        assert items[0]["status"] == "ready"

        # tree
        r = client.get(f"/api/code/project/{pid}", headers=_auth_headers(token))
        tree = r.get_json()["tree"]
        paths = {n["path"]: n for n in tree}
        assert "player/player.gd" in paths
        assert paths["player/player.gd"]["type"] == "file"
        assert paths["player"]["type"] == "dir"
        assert paths["player/player.gd"]["ai_summary"]

        # file content
        r = client.get(f"/api/code/project/{pid}/file?path=player/player.gd", headers=_auth_headers(token))
        fdata = r.get_json()
        assert fdata["content"].startswith("extends CharacterBody2D")
        assert fdata["ai_line_comments"]["1"] == "Класс игрока"


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_comment_flow(mock_ai, mock_clone, tmp_path):
    def _fake_clone(url, dest, timeout=30):
        _fake_godot_repo(dest)
        return True

    mock_clone.side_effect = _fake_clone
    mock_ai.return_value = _AI_FILE_RESPONSE

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _create_user(client)
        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/fake"},
                        headers=_auth_headers(token))
        pid = r.get_json()["project_id"]

        # add comment
        r = client.post(f"/api/code/project/{pid}/comment",
                        json={"file_path": "player/player.gd", "line_start": 2, "line_end": 4,
                              "comment": "Здесь настраивается скорость"}, headers=_auth_headers(token))
        assert r.status_code == 200
        cid = r.get_json()["id"]

        r = client.get(f"/api/code/project/{pid}/file?path=player/player.gd", headers=_auth_headers(token))
        uc = r.get_json()["user_comments"]
        assert len(uc) == 1
        assert uc[0]["comment"] == "Здесь настраивается скорость"
        assert uc[0]["line_start"] == 2

        # comment count appears in tree
        r = client.get(f"/api/code/project/{pid}", headers=_auth_headers(token))
        node = [n for n in r.get_json()["tree"] if n["path"] == "player/player.gd"][0]
        assert node["comment_count"] == 1

        # delete comment
        r = client.delete(f"/api/code/project/{pid}/comment/{cid}", headers=_auth_headers(token))
        assert r.status_code == 200
        r = client.get(f"/api/code/project/{pid}/file?path=player/player.gd", headers=_auth_headers(token))
        assert len(r.get_json()["user_comments"]) == 0


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_project_delete(mock_ai, mock_clone, tmp_path):
    def _fake_clone(url, dest, timeout=30):
        _fake_godot_repo(dest)
        return True

    mock_clone.side_effect = _fake_clone
    mock_ai.return_value = _AI_FILE_RESPONSE

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _create_user(client)
        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/fake"},
                        headers=_auth_headers(token))
        pid = r.get_json()["project_id"]

        r = client.delete(f"/api/code/project/{pid}", headers=_auth_headers(token))
        assert r.status_code == 200
        r = client.get("/api/code/projects", headers=_auth_headers(token))
        assert len(r.get_json()["items"]) == 0


def test_auth_required():
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        assert client.get("/api/code/projects").status_code == 401
        assert client.post("/api/code/analyze", json={"repo_url": "https://x.com/y"}).status_code == 401
        assert client.get("/api/code/project/1").status_code == 401


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_validation(mock_ai, mock_clone):
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _create_user(client)

        r = client.post("/api/code/analyze", json={"repo_url": "not-a-url"}, headers=_auth_headers(token))
        assert r.status_code == 400

        r = client.post("/api/code/analyze", json={}, headers=_auth_headers(token))
        assert r.status_code == 400

        r = client.post("/api/code/project/999/comment",
                        json={"file_path": "a.gd", "comment": "x"}, headers=_auth_headers(token))
        assert r.status_code == 404

        r = client.get("/api/code/project/999", headers=_auth_headers(token))
        assert r.status_code == 404


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_other_user_cannot_access(mock_ai, mock_clone, tmp_path):
    def _fake_clone(url, dest, timeout=30):
        _fake_godot_repo(dest)
        return True

    mock_clone.side_effect = _fake_clone
    mock_ai.return_value = _AI_FILE_RESPONSE

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _create_user(client)
        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/fake"},
                        headers=_auth_headers(token))
        pid = r.get_json()["project_id"]

        # second user
        r2 = client.post("/api/auth/register", json={"login": "code_user2", "password": "pass1234", "email": "c2@test.local"})
        token2 = r2.get_json()["token"]

        r = client.get(f"/api/code/project/{pid}", headers=_auth_headers(token2))
        assert r.status_code == 404
        r = client.delete(f"/api/code/project/{pid}", headers=_auth_headers(token2))
        assert r.status_code == 404


@patch("api.index._code_clone_repo")
def test_degraded_ai_fallback(mock_clone, tmp_path):
    def _fake_clone(url, dest, timeout=30):
        _fake_godot_repo(dest)
        return True

    mock_clone.side_effect = _fake_clone

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine), patch("api.index._code_ai_call", return_value="не JSON"):
        client = app.test_client()
        token = _create_user(client)
        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/fake"},
                        headers=_auth_headers(token))
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        # fallback summary is still stored
        r = client.get(f"/api/code/project/{data['project_id']}/file?path=player/player.gd",
                       headers=_auth_headers(token))
        assert "анализ недоступен" in r.get_json()["ai_summary"]