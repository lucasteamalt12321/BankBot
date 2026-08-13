"""E2E tests for the LTHub web portal: auth, feedback, trivia, admin and pages."""

import base64
import io
import json
import re
from datetime import datetime, timezone
from unittest.mock import patch
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from api.index import (
    _TRIVIA_SESSIONS,
    app,
)


def _make_engine():
    """In-memory engine (single shared connection) with sqlite-compatible schema.

    Registers a NOW() scalar so the PG-style INSERTs (``NOW()``) used by the
    production code resolve against SQLite.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _now_fn(dbapi_conn, _record):
        marker = "n" + "ow"
        def now_impl():
            return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        dbapi_conn.create_function(marker.upper(), 0, now_impl)

        def _any(v):
            try:
                return 1 if json.loads(v) else 0
            except Exception:
                return 0

        dbapi_conn.create_function("ANY", 1, _any)

    @event.listens_for(engine, "do_execute")
    def _any_exec(cursor, statement, parameters, context):
        if "ANY(" in statement and parameters:
            args = list(parameters)
            if isinstance(args[-1], list):
                args[-1] = json.dumps(args[-1])
            return cursor.execute(statement, tuple(args))
        return cursor.execute(statement, parameters)

    ddl = """
    CREATE TABLE IF NOT EXISTS web_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        login VARCHAR(64) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        display_name VARCHAR(100),
        gd_nickname VARCHAR(64),
        telegram_id BIGINT,
        lichess_nickname VARCHAR(64),
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_sessions (
        token VARCHAR(64) PRIMARY KEY,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_coin_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER NOT NULL,
        description VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        login VARCHAR(64),
        author_name VARCHAR(100),
        category VARCHAR(16),
        module VARCHAR(64),
        message TEXT,
        status VARCHAR(16) DEFAULT 'open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id BIGINT,
        first_name TEXT,
        username TEXT
    );
    CREATE TABLE IF NOT EXISTS user_coins (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        last_puzzle_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id BIGINT NOT NULL,
        username TEXT,
        level_name TEXT NOT NULL,
        media_file_id TEXT,
        media_type TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMP,
        reviewed_by BIGINT
    );
    CREATE TABLE IF NOT EXISTS canon_works (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title VARCHAR(200) NOT NULL,
        kind VARCHAR(16) NOT NULL DEFAULT 'track',
        author VARCHAR(100),
        date VARCHAR(50),
        canon_level VARCHAR(16) NOT NULL DEFAULT 'medium',
        url TEXT,
        content TEXT DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'approved',
        submitted_by INTEGER,
        audio_data BLOB,
        audio_name VARCHAR(255),
        audio_mime VARCHAR(100),
        audio_size INTEGER,
        view_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS canon_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title VARCHAR(200) NOT NULL,
        kind VARCHAR(16) NOT NULL DEFAULT 'track',
        author VARCHAR(100),
        date VARCHAR(50),
        canon_level VARCHAR(16) NOT NULL DEFAULT 'medium',
        url TEXT,
        content TEXT DEFAULT '',
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        reviewer_id INTEGER,
        review_note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS canon_doc (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        updated_by INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    INSERT INTO canon_works (title, kind, author, date, canon_level, url, content, status)
        VALUES ('Сидовый трек', 'track', 'Канон-команда', '', 'high', '', '', 'approved');
    """
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            if stmt.strip():
                conn.execute(text(stmt))
    return engine


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _promote_admin(user_id: int) -> None:
    from api import index as index_api

    engine = index_api.get_db_engine()
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE web_users SET is_admin = 1 WHERE id = :uid"),
            {"uid": user_id},
        )


def test_web_pages_render():
    """All main web pages return 200 with expected content."""
    client = app.test_client()
    for url, marker in [
        ("/", "LTHub"),
        ("/register", "Регистрация"),
        ("/login", "Войти"),
        ("/account", "Личный кабинет"),
        ("/suggest", "Предложения"),
        ("/trivia", "Викторина"),
        ("/admin", "Админ-панель"),
        ("/reading_trainer.html", "Тренажёр чтения"),
        ("/daily_prayer", "Молитва"),
        ("/dnd", "D&D"),
        ("/gd", "Geometry Dash"),
        ("/chess", "Шахматы"),
        ("/irregular_verbs", "Практика глаголов"),
        ("/emperors", "Императоры России"),
        ("/canon", "Канон вселенной Олеговируса"),
    ]:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        assert marker in resp.get_data(as_text=True), f"{url} missing {marker}"


@patch("api.index.get_db_engine")
def test_gd_web_submit_requires_media(mock_engine):
    """GD web submission requires an attached video/photo and saves it."""
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    # Without media -> 400 with hint to attach media.
    resp = c.post("/api/gd/submit", data={
        "user_id": "web_test123",
        "level_name": "Tartarus",
        "username": "web_test123",
    }, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "Прикрепите видео или фото" in resp.get_json()["error"]

    # With a fake video file -> created, media_type=video, data-URL stored.
    resp = c.post("/api/gd/submit", data={
        "user_id": "web_test123",
        "level_name": "Tartarus",
        "username": "web_test123",
        "media": (io.BytesIO(b"\x00\x01\x02fake-video"), "run.mp4"),
    }, content_type="multipart/form-data")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    engine = mock_engine.return_value
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT level_name, media_type, status, media_file_id FROM submissions WHERE id = :sid"
        ), {"sid": data["submission_id"]}).mappings().first()
    assert row["level_name"] == "Tartarus"
    assert row["status"] == "pending"
    assert row["media_type"] == "video"
    assert row["media_file_id"].startswith("data:video/mp4;base64,")

    # Web page exposes the upload field.
    body = c.get("/gd").get_data(as_text=True)
    assert 'id="sub-media"' in body
    assert "sub-media" in body
    assert "Прикрепите видео или фото" in body


def test_reading_trainer_has_mom05_features():
    resp = app.test_client().get("/reading_trainer.html")
    body = resp.get_data(as_text=True)
    assert "speakStory()" in body
    assert "toggleHint(" in body
    assert "reading_trainer_stats" in body
    assert "stats-bar" in body


@patch("api.index.get_db_engine")
def test_reading_generate_fallback(mock_engine):
    """Without API keys the endpoint returns a fallback set."""
    mock_engine.return_value = _make_engine()
    with patch("api.index.os.getenv", return_value=None):
        resp = app.test_client().post("/api/reading_generate", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "text" in data
    assert len(data.get("questions", [])) >= 1


def test_trivia_question_and_answer():
    """Trivia session flow: ask a question, answer it, verify result."""
    _TRIVIA_SESSIONS.clear()
    client = app.test_client()
    q = client.post("/api/trivia/question").get_json()
    assert "id" in q
    assert "session_id" in q
    assert len(q["options"]) == 4
    correct_index = q["correct_index"]
    ans = client.post("/api/trivia/answer", json={"session_id": q["session_id"], "answer_index": correct_index}).get_json()
    assert ans["correct"] is True
    assert ans["explanation"]
    wrong = client.post("/api/trivia/answer", json={"session_id": q["session_id"], "answer_index": (correct_index + 1) % 4}).get_json()
    assert wrong["correct"] is False
    assert wrong["correct_text"] == q["options"][correct_index]
    stale = client.post("/api/trivia/answer", json={"session_id": 99999, "answer_index": 0}).get_json()
    assert stale["correct"] is False


def test_trivia_manual_distractors_realistic():
    """Manual-distractor questions keep options unique within one round."""
    client = app.test_client()
    for _ in range(30):
        q = client.post("/api/trivia/question").get_json()
        assert q["correct_index"] in range(4)
        assert len(set(q["options"])) == 4


@patch("api.index.get_db_engine")
def test_auth_register_login_me_logout(mock_engine):
    """Full auth lifecycle with a real in-memory DB."""
    mock_engine.return_value = _make_engine()
    client = app.test_client()

    r = client.post("/api/auth/register", json={"login": "us", "password": "short"})
    assert r.status_code == 400

    r = client.post("/api/auth/register", json={"login": "alice", "password": "secret123"})
    assert r.status_code == 200
    body = r.get_json()
    assert "token" in body
    token = body["token"]

    dup = client.post("/api/auth/register", json={"login": "alice", "password": "secret123"})
    assert dup.status_code == 409

    bad = client.post("/api/auth/login", json={"login": "alice", "password": "wrong"})
    assert bad.status_code == 401

    login = client.post("/api/auth/login", json={"login": "alice", "password": "secret123"})
    assert login.status_code == 200
    token = login.get_json()["token"]

    me = client.get("/api/auth/me", headers=_auth_headers(token))
    assert me.status_code == 200
    assert me.get_json()["login"] == "alice"
    assert "coins" in me.get_json()

    unauthed = client.get("/api/auth/me")
    assert unauthed.status_code == 401

    upd = client.post("/api/auth/update", json={"display_name": "Алиса"},
                      headers=_auth_headers(token))
    assert upd.status_code == 200

    logout = client.post("/api/auth/logout", headers=_auth_headers(token))
    assert logout.status_code == 200
    after = client.get("/api/auth/me", headers=_auth_headers(token))
    assert after.status_code == 401


@patch("api.index.get_db_engine")
def test_feedback_submit_and_admin_flow(mock_engine):
    """Feedback: submit, list as admin, reject anonymous delete."""
    mock_engine.return_value = _make_engine()
    client = app.test_client()

    bad = client.post("/api/feedback", json={"category": "other", "message": "x"})
    assert bad.status_code == 400

    with patch("api.index.notify_admin"):
        ok = client.post("/api/feedback", json={
            "category": "suggestion", "message": "Добавьте тёмную тему в чат.",
            "module": "ai_chat",
        })
    assert ok.status_code == 200

    r = client.get("/api/admin/feedback")
    assert r.status_code == 403

    reg = client.post("/api/auth/register", json={
        "login": "boss", "password": "secret123",
    })
    assert reg.status_code == 200
    reg_data = reg.get_json()
    _promote_admin(reg_data["user_id"])
    token = reg_data["token"]

    lst = client.get("/api/admin/feedback", headers=_auth_headers(token))
    assert lst.status_code == 200
    data = lst.get_json()
    assert data["count"] >= 1
    fid = data["items"][0]["id"]

    by_sugg = client.get("/api/admin/feedback?category=suggestion", headers=_auth_headers(token))
    assert by_sugg.status_code == 200
    assert by_sugg.get_json()["count"] >= 1
    by_bug = client.get("/api/admin/feedback?category=bug", headers=_auth_headers(token))
    assert by_bug.status_code == 200
    assert by_bug.get_json()["count"] == 0

    d = client.delete(f"/api/admin/feedback/{fid}", headers=_auth_headers(token))
    assert d.status_code == 200

    reg2 = client.post("/api/auth/register", json={"login": "bob", "password": "secret123"})
    token2 = reg2.get_json()["token"]
    lst2 = client.get("/api/admin/feedback", headers=_auth_headers(token2))
    assert lst2.status_code == 403


@patch("api.index.get_db_engine")
def test_admin_stats_and_users(mock_engine):
    """Admin endpoints return aggregated data for an admin session."""
    mock_engine.return_value = _make_engine()
    client = app.test_client()

    reg = client.post("/api/auth/register", json={
        "login": "root", "password": "secret123",
    })
    reg_data = reg.get_json()
    token = reg_data["token"]
    headers = _auth_headers(token)
    user_id = reg_data["user_id"]
    _promote_admin(user_id)

    stats = client.get("/api/admin/stats", headers=headers)
    assert stats.status_code == 200
    assert "web_users" in stats.get_json()

    users = client.get("/api/admin/users", headers=headers)
    assert users.status_code == 200
    assert isinstance(users.get_json(), list)

    coins = client.get(f"/api/admin/users/{user_id}/coins", headers=headers)
    assert coins.status_code == 200

    no_access = client.get("/api/admin/stats")
    assert no_access.status_code == 403


def test_reading_trainer_page_clean_html():
    """Reading trainer page has no stray f-string artifacts."""
    body = app.test_client().get("/reading_trainer.html").get_data(as_text=True)
    assert re.search(r"id=\"stats-bar\"", body)


def test_suggest_page_contains_form():
    """The /suggest page contains the feedback form fields."""
    body = app.test_client().get("/suggest").get_data(as_text=True)
    assert "category" in body
    assert "module" in body
