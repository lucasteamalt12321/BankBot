"""Tests for the Code Explainer module."""

import json
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from api.index import app, _AI_RATE_LIMITS


@pytest.fixture(autouse=True)
def _reset_ai_rate():
    _AI_RATE_LIMITS.clear()
    yield
    _AI_RATE_LIMITS.clear()


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
        created_via VARCHAR(32),
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
        user_id BIGINT,
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
        ai_chunks_done INTEGER NOT NULL DEFAULT 0,
        ai_chunks_total INTEGER NOT NULL DEFAULT 1,
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
    CREATE TABLE IF NOT EXISTS code_chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        user_id BIGINT NOT NULL,
        role VARCHAR(16) NOT NULL,
        content TEXT NOT NULL,
        tool_calls TEXT,
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


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_auth_required(mock_ai, mock_clone):
    mock_clone.side_effect = lambda url, dest, timeout=30: False
    mock_ai.return_value = "{}"
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        # список проектов свободен для анонимов (гостевые анализы)
        assert client.get("/api/code/projects").status_code == 200
        # гостевой анализ разрешён (без ИИ): это не 401
        r = client.post("/api/code/analyze", json={"repo_url": "https://x.com/y"})
        assert r.status_code != 401
        # гостевой публичный проект виден анонимам
        assert client.get("/api/code/project/1").status_code == 200


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
        assert "GDScript" in r.get_json()["ai_summary"]


def test_artifacts_skipped_and_all_files_stored():
    """Chat exports, lock files and min assets are skipped; every code file is stored."""
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine), \
         patch("api.index._code_clone_repo") as mock_clone, \
         patch("api.index._code_ai_call") as mock_ai:
        def _fake_clone(url, dest, timeout=30):
            _fake_godot_repo(dest)
            os.makedirs(os.path.join(dest, "data", "chat_export"), exist_ok=True)
            with open(os.path.join(dest, "data", "chat_export", "room1.html"), "w", encoding="utf-8") as fh:
                fh.write("<html>" + ("x" * 5000) + "</html>")
            with open(os.path.join(dest, "package-lock.json"), "w", encoding="utf-8") as fh:
                fh.write("{}")
            with open(os.path.join(dest, "player", "player.min.js"), "w", encoding="utf-8") as fh:
                fh.write("var a=1;")
            with open(os.path.join(dest, "player", "extra.gd"), "w", encoding="utf-8") as fh:
                fh.write("extends Node\n\nfunc _ready():\n    pass\n")
            return True

        mock_clone.side_effect = _fake_clone
        mock_ai.return_value = _AI_FILE_RESPONSE
        client = app.test_client()
        token = _create_user(client)
        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/fake"},
                        headers=_auth_headers(token))
        pid = r.get_json()["project_id"]
        r = client.get(f"/api/code/project/{pid}", headers=_auth_headers(token))
        paths = {n["path"]: n for n in r.get_json()["tree"]}
        assert "player/extra.gd" in paths
        assert "player/player.gd" in paths
        assert "player/player.min.js" not in paths
        assert "package-lock.json" not in paths
        assert "data/chat_export/room1.html" not in paths


def test_large_file_chunking_and_resume():
    """Large files are chunked; re-analyze resumes from where it stopped."""
    engine = _make_engine()
    big_file = "\n".join(f"line {i}" for i in range(9500))

    from api.index import _code_chunks_total, _code_persist_files, _CODE_CHUNKS_PER_RUN

    large_resp = json.dumps({
        "files": {
            "player/big.gd": {"summary": "Большой файл: начало.", "line_comments": {"30": "Строка 30"}}
        }
    })

    repo_files = [
        {"path": "player/big.gd", "lang_key": "gd", "line_count": 9500, "content": big_file},
        {"path": "player/player.gd", "lang_key": "gd", "line_count": 7,
         "content": "extends CharacterBody2D\n\nvar speed = 300\n"},
    ]

    with patch("api.index.get_db_engine", return_value=engine), \
         patch("api.index._code_ai_call", return_value=large_resp):
        stats = _code_persist_files(1, repo_files, run_ai=True)
    assert stats["file_count"] == 2
    assert stats["analyzed_count"] >= 1

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT ai_chunks_done, ai_chunks_total FROM code_files "
            "WHERE project_id = 1 AND file_path = 'player/big.gd'"
        )).mappings().first()
    done, total = int(row["ai_chunks_done"]), int(row["ai_chunks_total"])
    assert total == _code_chunks_total(9500)
    assert done == _CODE_CHUNKS_PER_RUN  # chunk budget consumed
    assert done < total

    # resumes from the stored progress
    with patch("api.index.get_db_engine", return_value=engine), \
         patch("api.index._code_ai_call", return_value=large_resp):
        _code_persist_files(1, repo_files, run_ai=True)
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT ai_chunks_done, ai_chunks_total FROM code_files "
            "WHERE project_id = 1 AND file_path = 'player/big.gd'"
        )).mappings().first()
    done2 = int(row["ai_chunks_done"])
    assert done2 > done
    assert done2 <= total


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
@patch("api.index._ai_chat")
def test_chat_flow(mock_ai_chat, mock_ai, mock_clone, tmp_path):
    def _fake_clone(url, dest, timeout=30):
        _fake_godot_repo(dest)
        return True

    mock_clone.side_effect = _fake_clone
    mock_ai.return_value = _AI_FILE_RESPONSE

    class _FakeResp:
        def __init__(self, text):
            self._text = text

        @property
        def status_code(self):
            return 200

        def json(self):
            return {"choices": [{"message": {"content": self._text}}]}

    # First turn: AI calls read_file tool; second turn: AI answers the question.
    mock_ai_chat.side_effect = [
        _FakeResp(json.dumps({"tool": "read_file", "path": "player/player.gd"})),
        _FakeResp("Класс Игрока отвечает за движение и здоровье персонажа."),
    ]

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        with patch("api.index._AI_RATE_LIMITS", new_callable=dict) as _:
            client = app.test_client()
            token = _create_user(client)
            r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/fake"},
                            headers=_auth_headers(token))
            pid = r.get_json()["project_id"]

            r = client.post(f"/api/code/project/{pid}/chat", json={"message": "Что делает player.gd?"},
                            headers=_auth_headers(token))
            assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] is True
        assert "движение" in d["reply"]

        # empty message -> 400
        r = client.post(f"/api/code/project/{pid}/chat", json={"message": ""},
                        headers=_auth_headers(token))
        assert r.status_code == 400

        # AI reads the file and adds a comment
        mock_ai_chat.side_effect = [
            _FakeResp(json.dumps({"tool": "add_comment", "path": "player/player.gd", "line": 3, "comment": "Скорость экспортирована"})),
            _FakeResp("Комментарий добавлен."),
        ]
        r = client.post(f"/api/code/project/{pid}/chat", json={"message": "Добавь комментарий к скорости"},
                        headers=_auth_headers(token))
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        r = client.get(f"/api/code/project/{pid}/file?path=player/player.gd", headers=_auth_headers(token))
        uc = r.get_json()["user_comments"]
        assert any(c["comment"] == "Скорость экспортирована" for c in uc)


def _fake_repo_with_big_file(dest):
    """Fake repo: big.py (900 lines — «большой файл») + main.py (маленький)."""
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "main.py"), "w", encoding="utf-8") as fh:
        fh.write("def run():\n    return 1\n")
    with open(os.path.join(dest, "big.py"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(f"x{i} = {i}" for i in range(900)))


_BIG_AI_RESPONSE = json.dumps({
    "files": {
        "main.py": {
            "summary": "Главный модуль.",
            "line_comments": {"1": "Функция run"},
        }
    }
})


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_guest_scan_skips_large_files(mock_ai, mock_clone, tmp_path):
    """Аноним: загрузка (analyze:false) + «Разобрать» — большие файлы (>800 строк) пропущены, малые проанализированы."""
    def _fake_clone(url, dest, timeout=30):
        _fake_repo_with_big_file(dest)
        return True

    mock_clone.side_effect = _fake_clone
    mock_ai.return_value = _BIG_AI_RESPONSE

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()

        # аноним грузит проект (гостевой, user_id NULL, без ИИ)
        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/big", "analyze": False})
        assert r.status_code == 200, r.get_json()
        pid = r.get_json()["project_id"]

        # аноним «разбирает» проект: большие файлы пропускаются
        r = client.post(f"/api/code/project/{pid}/analyze")
        assert r.status_code == 200, r.get_json()
        d = r.get_json()
        assert d["ok"] is True
        assert d["skipped_large"] == 1
        assert d["file_count"] == 1  # только main.py в пуле скана
        assert d["analyzed_count"] == 1

        # main.py получил ИИ-комментарий
        r = client.get(f"/api/code/project/{pid}/file?path=main.py")
        fdata = r.get_json()
        assert fdata["ai_line_comments"].get("1") == "Функция run"

        # big.py НЕ анализировался (чанки не прогрессировали)
        r = client.get(f"/api/code/project/{pid}/file?path=big.py")
        bdata = r.get_json()
        assert not bdata["ai_line_comments"]


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_guest_cannot_scan_owned_project(mock_ai, mock_clone, tmp_path):
    """Аноним не может сканировать проект, загруженный зарегистрированным пользователем."""
    def _fake_clone(url, dest, timeout=30):
        _fake_repo_with_big_file(dest)
        return True

    mock_clone.side_effect = _fake_clone
    mock_ai.return_value = _BIG_AI_RESPONSE

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _create_user(client)
        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/owned"},
                        headers=_auth_headers(token))
        pid = r.get_json()["project_id"]

        # аноним пытается сканировать личный проект → 404
        r = client.post(f"/api/code/project/{pid}/analyze")
        assert r.status_code == 404
        assert r.get_json()["error"] == "Проект не найден"


@patch("api.index._code_clone_repo")
@patch("api.index._code_ai_call")
def test_guest_scan_rate_limited(mock_ai, mock_clone, tmp_path):
    """Гостевой скан ограничен по IP: после _CODE_GUEST_SCAN_RATE вызовов → 429."""
    def _fake_clone(url, dest, timeout=30):
        _fake_repo_with_big_file(dest)
        return True

    mock_clone.side_effect = _fake_clone
    mock_ai.return_value = _BIG_AI_RESPONSE

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        r = client.post("/api/code/analyze", json={"repo_url": "https://github.com/x/big", "analyze": False})
        pid = r.get_json()["project_id"]

        from api.index import _CODE_GUEST_SCAN_RATE
        for _ in range(_CODE_GUEST_SCAN_RATE):
            r = client.post(f"/api/code/project/{pid}/analyze")
            assert r.status_code == 200, r.get_json()

        r = client.post(f"/api/code/project/{pid}/analyze")
        assert r.status_code == 429


def _seed_project(engine, uid):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO code_projects (user_id, repo_url, repo_name, status, file_count) "
            "VALUES (:uid, 'https://github.com/x/seed', 'seed', 'ready', 0)"
        ), {"uid": uid})
        pid = conn.execute(text("SELECT MAX(id) FROM code_projects")).scalar()
    return pid


def _seed_file(engine, pid, path, lang, line_count, content, done=0, total=1, summary=""):
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO code_files (project_id, file_path, file_type, parent_path, language, "
            "line_count, content, ai_summary, ai_line_comments, ai_chunks_done, ai_chunks_total) "
            "VALUES (:pid, :path, 'file', :parent, :lang, :lc, :content, :summary, '{}', :done, :total)"
        ), {"pid": pid, "path": path, "parent": "/".join(path.split("/")[:-1]),
            "lang": lang, "lc": line_count, "content": content, "summary": summary,
            "done": done, "total": total})


@patch("api.index._code_ai_call")
def test_reanalyze_advances_past_first_35_files(mock_ai):
    """«Анализировать всё»: пул — недокрытые файлы, а не всегда первые 35; прогресс растёт до 100%."""
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _create_user(client)
        with engine.connect() as conn:
            uid = conn.execute(text("SELECT id FROM web_users WHERE login='code_user'")).scalar()

    pid = _seed_project(engine, uid)
    for i in range(35):
        _seed_file(engine, pid, f"src/mod{i}.py", ".py", 10, f"def f{i}():\n    return {i}\n",
                   done=1, total=1, summary=f"Модуль {i}")
    _seed_file(engine, pid, "tests/zzz_unanalyzed.py", ".py", 10, "def helper():\n    return 1\n")

    mock_ai.return_value = json.dumps({"files": {
        "tests/zzz_unanalyzed.py": {"summary": "Вспомогательный тестовый модуль.",
                                    "line_comments": {"1": "Функция helper"}}
    }})

    with patch("api.index.get_db_engine", return_value=engine):
        r = client.post(f"/api/code/project/{pid}/analyze", headers=_auth_headers(token))
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["ok"] is True
    assert d["file_count"] == 36
    assert d["analyzed_count"] == 36  # регресс-фикс: анализ дошёл до конца, а не застрял на 35

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT ai_chunks_done, ai_summary FROM code_files "
            "WHERE project_id = :pid AND file_path = 'tests/zzz_unanalyzed.py'"
        ), {"pid": pid}).mappings().first()
    assert int(row["ai_chunks_done"]) == 1
    assert "тестовый" in (row["ai_summary"] or "")


@patch("api.index._code_ai_call")
def test_reanalyze_resumes_chunked_file(mock_ai):
    """Анализ большого файла продолжается с хранимого прогресса, а не перечитывает готовые чанки."""
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        token = _create_user(client)
        with engine.connect() as conn:
            uid = conn.execute(text("SELECT id FROM web_users WHERE login='code_user'")).scalar()

    pid = _seed_project(engine, uid)
    _seed_file(engine, pid, "src/big.py", ".py", 1000,
               "\n".join(f"line {i}" for i in range(1000)), done=1, total=3)

    captured = {}

    def _fake_ai(prompt, max_tokens=1600):
        captured["prompt"] = prompt
        return json.dumps({"files": {"src/big.py": {
            "summary": "Большой модуль.", "line_comments": {"460": "Строка 460"}}}})

    mock_ai.side_effect = _fake_ai

    with patch("api.index.get_db_engine", return_value=engine):
        r = client.post(f"/api/code/project/{pid}/analyze", headers=_auth_headers(token))
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["file_count"] == 1
    assert d["analyzed_count"] == 1

    prompt = captured["prompt"]
    assert "фрагмент 2/3, строки 451–900" in prompt
    assert "фрагмент 1/3" not in prompt  # resume не перечитывает уже готовый фрагмент

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT ai_chunks_done, ai_chunks_total FROM code_files "
            "WHERE project_id = :pid AND file_path = 'src/big.py'"
        ), {"pid": pid}).mappings().first()
    assert int(row["ai_chunks_done"]) == int(row["ai_chunks_total"]) == 3


def test_infer_summary_languages():
    """"Хирургические" сводки для html/py/js/json вместо бессодержательных «Файл X — N строк»."""
    from api.index import _code_heuristic_summary

    cases = [
        ({"path": "site/index.html", "lang_key": ".html",
          "content": "<html><head><title>Магазин игрушек</title></head><body></body></html>"},
         "Магазин игрушек"),
        ({"path": "app/main.py", "lang_key": ".py",
          "content": "def run():\n    return 1\nclass Runner:\n    pass\n"},
         "функции: run"),
        ({"path": "app/main.py", "lang_key": ".py",
          "content": "class Runner:\n    def go(self):\n        pass\n"},
         "классы: Runner"),
        ({"path": "cfg/data.json", "lang_key": ".json",
          "content": '{"name": "bot", "port": 80}'},
         "ключи: name, port"),
        ({"path": "web/app.js", "lang_key": ".js",
          "content": "const PORT = 3000;\nexport function start() {}\n"},
         "start"),
        ({"path": "docs/note.md", "lang_key": ".md",
          "content": "# Установка\n## Запуск\n"},
         "Установка"),
    ]
    for info, needle in cases:
        out, _ = _code_heuristic_summary(info)
        assert needle in out, (info["path"], out)
        assert " — " in out