"""E2E tests for the LTHub web portal: auth, feedback, trivia, admin and pages."""

import base64
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from api.index import (
    _AI_RATE_LIMITS,
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
        email VARCHAR(255) UNIQUE,
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
    CREATE TABLE IF NOT EXISTS friend_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER NOT NULL,
        to_user INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        friend_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS web_activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        module TEXT NOT NULL,
        actions INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS web_streak (
        user_id INTEGER PRIMARY KEY,
        last_active_day TEXT NOT NULL,
        current_streak INTEGER NOT NULL DEFAULT 0,
        longest_streak INTEGER NOT NULL DEFAULT 0,
        total_active_days INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS web_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        unlocked_at REAL NOT NULL
    );
    CREATE UNIQUE INDEX IF NOT EXISTS uq_friend_requests_pair ON friend_requests(from_user, to_user);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_web_friends_pair ON web_friends(user_id, friend_id);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_web_achievements_user_code ON web_achievements(user_id, code);
    CREATE UNIQUE INDEX IF NOT EXISTS uq_web_activity_user_day_module ON web_activity_log(user_id, day, module);
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
        difficulty TEXT,
        attempts INTEGER,
        media_file_id TEXT,
        media_type TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMP,
        reviewed_by BIGINT
    );
    CREATE TABLE IF NOT EXISTS levels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position INTEGER NOT NULL DEFAULT 0,
        difficulty TEXT DEFAULT 'Unknown'
    );
    CREATE TABLE IF NOT EXISTS level_completions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id BIGINT NOT NULL,
        level_id INTEGER NOT NULL,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        player_name TEXT,
        UNIQUE(user_id, level_id)
    );
    CREATE TABLE IF NOT EXISTS player_stats (
        user_id BIGINT PRIMARY KEY,
        total_approved INTEGER DEFAULT 0,
        total_rejected INTEGER DEFAULT 0,
        hardest_level_id INTEGER,
        last_submission TIMESTAMP,
        points INTEGER DEFAULT 0,
        demons_count INTEGER DEFAULT 0
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
        ("/stats", "📊 Статистика"),
        ("/suggest", "Предложения"),
        ("/trivia", "Викторина"),
        ("/admin", "Админ-панель"),
        ("/reading_trainer.html", "Тренажёр чтения"),
        ("/daily_prayer", "Молитва"),
        ("/dnd", "D&D"),
        ("/gd", "Geometry Dash"),
        ("/chess", "Шахматы"),
        ("/irregular_verbs", "Практика глаголов"),
        ("/emperors", "История"),
        ("/canon", "Канон вселенной Олеговируса"),
    ]:
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} -> {resp.status_code}"
        assert marker in resp.get_data(as_text=True), f"{url} missing {marker}"


def test_account_page_has_stats_block():
    """Account page renders the general activity/stats block and OGE readiness section."""
    client = app.test_client()
    resp = client.get("/account")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "stats-box" in body
    assert "📊 Активность" in body
    assert "loadStats" in body


def test_stats_page_renders():
    """Standalone /stats page renders the general statistics shell."""
    client = app.test_client()
    resp = client.get("/stats")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "📊 Статистика" in body
    assert "mod-grid" in body
    assert "Календарь активности" in body
    assert "loadStats" not in body


@patch("api.index.get_db_engine")
def test_dnd_session_sharing_flow(mock_engine):
    """Host starts a session (gets share code/url); friend joins via code into the same session."""
    from api import dnd_runtime
    mock_engine.return_value = _make_engine()
    client = app.test_client()
    reg = client.post("/api/auth/register", json={
        "login": "dndhost", "password": "secret123", "email": "dnd@test.local",
    })
    headers = _auth_headers(reg.get_json()["token"])
    with patch.object(dnd_runtime, "cmd_dnd_start") as m_start, \
         patch.object(dnd_runtime, "find_active_session") as m_find, \
         patch.object(dnd_runtime, "find_session_by_code") as m_code, \
         patch.object(dnd_runtime, "join_session") as m_join, \
         patch.object(dnd_runtime, "get_session_log") as m_log, \
         patch.object(dnd_runtime, "get_session_players") as m_players:
        # Freemium 67/33: D&D sessions are only available to signed-in users.
        anon = client.post("/api/dnd/start", json={"user_id": "web_x", "name": "Подземелье"})
        assert anon.status_code == 401
        assert anon.get_json().get("auth_required") is True

        # Host starts a session
        m_start.return_value = "🎲 D&D сессия запущена!"
        m_find.return_value = {"id": 42, "name": "Подземелье", "share_code": "ABCD1234",
                                "current_scene": "Вход", "last_ai_response": ""}
        r = client.post("/api/dnd/start", json={"name": "Подземелье"}, headers=headers)
        assert r.status_code == 200
        d = r.get_json()
        assert d["share_code"] == "ABCD1234"
        assert d["share_url"] == "/dnd?session=ABCD1234"

        # Friend joins via the (case-insensitive) code
        m_code.return_value = {"id": 42, "name": "Подземелье", "status": "active", "share_code": "ABCD1234"}
        m_join.return_value = "✅ Вы присоединились к сессии «Подземелье»!"
        r2 = client.post("/api/dnd/join", json={"code": "abcd1234", "name": "Арден"}, headers=headers)
        assert r2.status_code == 200
        assert r2.get_json()["session_id"] == 42
        assert r2.get_json()["share_url"] == "/dnd?session=ABCD1234"

        # Friend's status shows the shared session with share_url and both players
        m_find.return_value = {"id": 42, "name": "Подземелье", "share_code": "ABCD1234",
                               "current_scene": "Вход", "last_ai_response": ""}
        m_players.return_value = [
            {"player_name": "host", "character_class": "Воин", "level": 1},
            {"player_name": "Арден", "character_class": "Воин", "level": 1},
        ]
        m_log.return_value = []
        r3 = client.get("/api/dnd/status", headers=headers)
        assert r3.status_code == 200
        sd = r3.get_json()
        assert sd["active"] is True
        assert sd["share_url"] == "/dnd?session=ABCD1234"
        assert len(sd["players"]) == 2

        # Unknown code -> 404
        m_code.return_value = None
        r4 = client.post("/api/dnd/join", json={"code": "ZZZZ0000"}, headers=headers)
        assert r4.status_code == 404


@patch("api.index.get_db_engine")
def test_gd_web_submit_requires_account_and_media(mock_engine):
    """GD web submission requires login, a GD nickname, and an attached video/photo."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        conn.execute(text("INSERT INTO web_users (id, login, password_hash, gd_nickname) VALUES (1, 'gduser', 'x', 'Riot')"))
        conn.execute(text("INSERT INTO web_users (id, login, password_hash) VALUES (2, 'gduser2', 'x')"))
    token = index_api._create_session(1)
    token2 = index_api._create_session(2)
    headers = _auth_headers(token)
    headers2 = _auth_headers(token2)

    # Anon (no token) -> 401, anonymous submissions forbidden.
    resp = c.post("/api/gd/submit", data={"level_name": "Tartarus"}, content_type="multipart/form-data")
    assert resp.status_code == 401
    assert "войти в аккаунт" in resp.get_json()["error"]

    # Authed but no media -> 400 hint to attach media.
    resp = c.post("/api/gd/submit", data={"level_name": "Tartarus"}, headers=headers, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "Прикрепите видео или фото" in resp.get_json()["error"]

    # Authed with gd_nickname in account + video -> created, username=gd_nickname, bound to account id.
    resp = c.post("/api/gd/submit", data={
        "level_name": "Tartarus",
        "media": (io.BytesIO(b"\x00\x01\x02fake-video"), "run.mp4"),
    }, headers=headers, content_type="multipart/form-data")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT user_id, username, level_name, media_type, status, media_file_id FROM submissions WHERE id = :sid"
        ), {"sid": data["submission_id"]}).mappings().first()
    assert row["user_id"] == 1
    assert row["username"] == "Riot"
    assert row["level_name"] == "Tartarus"
    assert row["status"] == "pending"
    assert row["media_type"] == "video"
    assert row["media_file_id"].startswith("data:video/mp4;base64,")

    # User without gd_nickname: submit without nick -> 400 gd_nickname_required.
    resp = c.post("/api/gd/submit", data={
        "level_name": "Tartarus",
        "media": (io.BytesIO(b"\x00\x01\x02fake-video"), "run.mp4"),
    }, headers=headers2, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert resp.get_json().get("gd_nickname_required") is True

    # Same user: submit WITH gd_nickname -> saved to account + created.
    resp = c.post("/api/gd/submit", data={
        "level_name": "Tartarus",
        "gd_nickname": "Neon",
        "media": (io.BytesIO(b"\x00\x01\x02fake-video"), "run.mp4"),
    }, headers=headers2, content_type="multipart/form-data")
    assert resp.status_code == 200
    with engine.connect() as conn:
        assert conn.execute(text("SELECT gd_nickname FROM web_users WHERE id = 2")).scalar() == "Neon"

    # Web page exposes the upload field.
    body = c.get("/gd").get_data(as_text=True)
    assert 'id="sub-media"' in body


@patch("api.index.get_db_engine")
def test_gd_web_submit_external_link_and_limits(mock_engine):
    """GD web submission accepts an external link instead of a file, with size/url limits."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO web_users (id, login, password_hash, gd_nickname) VALUES (1, 'gdlink', 'x', 'Riot')"))
    token = index_api._create_session(1)

    # Valid external link -> stored as-is with media_type=link.
    resp = c.post("/api/gd/submit", data={
        "level_name": "Tartarus",
        "media_url": "https://youtu.be/abc123?t=5",
        "token": token,
    }, content_type="multipart/form-data")
    assert resp.status_code == 200
    sid = resp.get_json()["submission_id"]
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT media_file_id, media_type, status FROM submissions WHERE id = :sid"
        ), {"sid": sid}).mappings().first()
    assert row["media_file_id"] == "https://youtu.be/abc123?t=5"
    assert row["media_type"] == "link"
    assert row["status"] == "pending"

    # Non-http(s) scheme -> 400.
    for bad_url in ("javascript:alert(1)", "data:text/html,<script>x</script>", "ftp://x/y", "//host/path"):
        resp = c.post("/api/gd/submit", data={
            "level_name": "Tartarus",
            "media_url": bad_url,
            "token": token,
        }, content_type="multipart/form-data")
        assert resp.status_code == 400, bad_url

    # File AND link together -> 400.
    resp = c.post("/api/gd/submit", data={
        "level_name": "Tartarus",
        "media_url": "https://youtu.be/abc",
        "media": (io.BytesIO(b"\x00\x01fake"), "run.mp4"),
        "token": token,
    }, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "один источник медиа" in resp.get_json()["error"]

    # File larger than 16MB -> 413.
    big = io.BytesIO(b"\x00" * (16 * 1024 * 1024 + 1))
    resp = c.post("/api/gd/submit", data={
        "level_name": "Tartarus",
        "media": (big, "run.mp4"),
        "token": token,
    }, content_type="multipart/form-data")
    assert resp.status_code == 413
    assert "16 МБ" in resp.get_json()["error"]

    # Page exposes both the file field and the link field.
    body = c.get("/gd").get_data(as_text=True)
    assert 'id="sub-media"' in body
    assert 'id="sub-link"' in body


@patch("api.index.get_db_engine")
def test_gd_level_completions_page_and_api(mock_engine):
    """Level page + API list approved completions with profile and media links."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        conn.execute(text("\n".join([
            "INSERT INTO web_users (id, login, password_hash, display_name, gd_nickname) VALUES (1, 'alice', 'x', 'Alice', 'Riot')",
        ])))
        conn.execute(text(
            "INSERT INTO users (id, telegram_id, first_name, username) VALUES (1, 777, 'Боб', 'bob_tg')"
        ))
    level_id = index_api.add_gd_level("Tartarus", 1, "Insane Demon")
    assert level_id is not None

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, username, level_name, media_file_id, media_type, status) "
            "VALUES (1, 1, 'Riot', 'Tartarus', 'https://youtu.be/abc', 'link', 'approved')"
        ))
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, username, level_name, media_file_id, media_type, status) "
            "VALUES (2, 777, 'TgBeast', 'Tartarus', 'data:image/png;base64,AAAA', 'photo', 'approved')"
        ))
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, username, level_name, media_file_id, media_type, status) "
            "VALUES (3, 1, 'Riot', 'Tartarus', 'data:video/mp4;base64,BBBB', 'video', 'pending')"
        ))

    # API: only approved, deduped per player, profile link for web user, tg user without profile.
    resp = c.get(f"/api/gd/level/{level_id}/completions")
    assert resp.status_code == 200
    d = resp.get_json()
    assert d["level"]["name"] == "Tartarus"
    assert d["level"]["difficulty"] == "Insane Demon"
    assert len(d["completions"]) == 2
    names = {u["player_name"] for u in d["completions"]}
    assert names == {"Riot", "TgBeast"}
    web = [u for u in d["completions"] if u["web_login"] == "alice"]
    assert web and web[0]["player_name"] == "Riot"
    assert web[0]["media_type"] == "link" and web[0]["media_file_id"] == "https://youtu.be/abc"
    tg = [u for u in d["completions"] if not u["web_login"]]
    assert tg and tg[0]["player_name"] == "TgBeast" and tg[0]["media_type"] == "photo"

    # Unknown level -> 404.
    assert c.get("/api/gd/level/999/completions").status_code == 404

    # Page renders; leaderboard links each level name to its page.
    rp = c.get(f"/gd/level/{level_id}")
    assert rp.status_code == 200
    assert "Прохождения уровня" in rp.get_data(as_text=True)
    gd_body = c.get("/gd").get_data(as_text=True)
    assert 'href="/gd/level/' in gd_body  # leaderboard level names link to the level page
    assert "Моя карточка" in gd_body and "Открыть полную карточку" in gd_body


@patch("api.index.get_db_engine")
def test_gd_normalized_difficulty(mock_engine):
    """Difficulty is normalized into the demon ladder; "Top X" tiers were removed."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    # Explicit tiers and legacy text maps to canonical keys.
    assert index_api._gd_norm_difficulty("Easy") == "easy"
    assert index_api._gd_norm_difficulty("Hard Demon") == "hard_demon"
    assert index_api._gd_norm_difficulty("extreme demon") == "extreme_demon"
    assert index_api._gd_norm_difficulty("insane_demon", 9) == "insane_demon"  # explicit wins

    # The retired "Top X" ladder is gone: legacy values/unknown resolve to "unknown".
    assert index_api._gd_norm_difficulty("Top 150") == "unknown"
    assert index_api._gd_norm_difficulty("Unknown", 1) == "unknown"
    assert index_api._gd_norm_difficulty("Unknown", 55) == "unknown"
    assert index_api._gd_norm_difficulty("Unknown", 200) == "unknown"
    assert index_api._gd_norm_difficulty("Unknown", 9999) == "unknown"

    # Level created with Unknown difficulty stays unknown (no auto-derived Top X).
    level_id = index_api.add_gd_level("Silent Clubstep", 3, "Unknown")
    assert level_id is not None
    resp = c.get(f"/api/gd/level/{level_id}/completions")
    assert resp.status_code == 200
    d = resp.get_json()
    assert d["level"]["difficulty_key"] == "unknown"
    assert d["level"]["difficulty"] == "Unknown"

    # Admin tier options no longer expose any "Top X" entries.
    opts = [o["key"] for o in index_api.gd_difficulty_options()]
    assert all(not k.startswith("top_") for k in opts)
    assert "extreme_demon" in opts

    # Fallback path: unreachable gdbrowser returns "Unknown" (and never hangs).
    with patch("api.index.requests.get", side_effect=Exception("offline")):
        assert index_api.get_gd_difficulty_name("Some Live Level") == "Unknown"


@patch("api.index.get_db_engine")
def test_gd_players_page_and_api(mock_engine):
    """Top players API/page + player card resolve local points, demons and completions."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO web_users (id, login, password_hash, display_name, gd_nickname) VALUES (1, 'alice', 'x', 'Alice', 'Riot')"
        ))
        conn.execute(text(
            "INSERT INTO users (id, telegram_id, first_name, username) VALUES (1, 777, 'Боб', 'bob_tg')"
        ))
    tartarus = index_api.add_gd_level("Tartarus", 1, "Extreme Demon")
    bloodbath = index_api.add_gd_level("Bloodbath", 2, "Unknown")
    assert tartarus is not None and bloodbath is not None

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO player_stats (user_id, points, demons_count, hardest_level_id) VALUES (1, 1000, 2, :t)"
        ), {"t": tartarus})
        conn.execute(text(
            "INSERT INTO player_stats (user_id, points, demons_count, hardest_level_id) VALUES (777, 500, 1, :t)"
        ), {"t": tartarus})
        conn.execute(text("INSERT INTO level_completions (user_id, level_id) VALUES (1, :t)"), {"t": tartarus})
        conn.execute(text("INSERT INTO level_completions (user_id, level_id) VALUES (1, :b)"), {"b": bloodbath})
        conn.execute(text("INSERT INTO level_completions (user_id, level_id) VALUES (777, :t)"), {"t": tartarus})

    resp = c.get("/api/gd/players")
    assert resp.status_code == 200
    players = resp.get_json()
    assert len(players) == 2
    top = players[0]
    assert top["rank"] == 1 and top["player_name"] == "Riot"
    assert top["points"] == 1500 and top["demons_count"] == 1 and top["web_login"] == "alice"
    assert "Tartarus" in top["hardest"]
    assert players[1]["player_name"] == "Боб" and players[1]["points"] == 1000

    # Players page.
    rp = c.get("/gd/players")
    assert rp.status_code == 200
    assert "Топ игроков" in rp.get_data(as_text=True)
    assert "/gd/player/" in rp.get_data(as_text=True)

    # Profile page embeds the GD player-card widget.
    up = c.get("/u/alice").get_data(as_text=True)
    assert "Карточка игрока GDL" in up and "/gd/player/" in up

    # Player card resolves web user by GD nick.
    prof = c.get("/api/gd/player/Riot").get_json()
    assert prof["found"] is True
    assert prof["player_name"] == "Riot"
    assert prof["points"] == 1500
    assert prof["demons_count"] == 1
    assert prof["completions_count"] == 2
    assert prof["web_login"] == "alice"
    assert "Tartarus" in prof["hardest"]
    diff_keys = {co["difficulty_key"] for co in prof["completions"]}
    assert "extreme_demon" in diff_keys

    # Unknown nick (no local record) -> found:False.
    nf = c.get("/api/gd/player/NoSuchPlayer123").get_json()
    assert nf["found"] is False

    # Player page renders.
    pbody = c.get("/gd/player/Riot").get_data(as_text=True)
    assert "Карточка игрока" in pbody


@patch("api.index.get_db_engine")
def test_gd_persona_attribution(mock_engine):
    """Completions are attributed by the GD nick from the approved submission (per-completion, not per-account)."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        for uid, first_name, username in ((111, "LucasTeam", "luke_tg"), (222, "TestRaven", "test_tg")):
            conn.execute(text(
                "INSERT INTO users (id, telegram_id, first_name, username) VALUES (:i, :i, :f, :u)"
            ), {"i": uid, "f": first_name, "u": username})
    supersonic = index_api.add_gd_level("Supersonic", 1, "Unknown")
    tvol = index_api.add_gd_level("True values of live", 2, "Unknown")
    assert supersonic is not None and tvol is not None

    # The same account finished both levels, but submitted under different GD nicks.
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, username, level_name, status, submitted_at) "
            "VALUES (1, 111, 'LucasTeam', 'Supersonic', 'approved', '2026-08-16 18:08:10')"
        ))
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, username, level_name, status, submitted_at) "
            "VALUES (2, 111, 'ShadowRaven', 'True values of live', 'approved', '2026-08-27 07:37:10')"
        ))
        conn.execute(text(
            "INSERT INTO level_completions (user_id, level_id, player_name) VALUES (111, :s, 'LucasTeam')"
        ), {"s": supersonic})
        conn.execute(text(
            "INSERT INTO level_completions (user_id, level_id, player_name) VALUES (111, :t, 'ShadowRaven')"
        ), {"t": tvol})

    # No account merging: each completion counts under its submission nick.
    players = c.get("/api/gd/players").get_json()
    by_nick = {p["player_name"]: p for p in players}
    assert by_nick["LucasTeam"]["points"] == 1000
    assert by_nick["ShadowRaven"]["points"] == 500
    assert by_nick["ShadowRaven"]["demons_count"] == 0
    assert by_nick["ShadowRaven"]["hardest"] == "True values of live (поз. 2)"

    # Player card resolves the nick to only its own completion.
    prof = c.get("/api/gd/player/ShadowRaven").get_json()
    assert prof["found"] is True and prof["player_name"] == "ShadowRaven"
    assert prof["points"] == 500 and prof["completions_count"] == 1
    assert [co["name"] for co in prof["completions"]] == ["True values of live"]

    # Level completions list shows the victor's submission nick.
    d = c.get(f"/api/gd/level/{supersonic}/completions").get_json()
    completers = [u["player_name"] for u in d["completions"]]
    assert completers == ["LucasTeam"]


@patch("api.index.get_db_engine")
def test_gd_players_casefold_merge(mock_engine):
    """Same persona in different cases is a single top entry, spelled with a capital letter."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO web_users (id, login, password_hash, display_name, gd_nickname) "
            "VALUES (1, 'nikiktos', 'x', 'ник', 'nikiktos')"
        ))
    pos5 = index_api.add_gd_level("Maethrillian", 5, "Unknown")
    pos8 = index_api.add_gd_level("Acid factory", 8, "Unknown")
    assert pos5 is not None and pos8 is not None

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO level_completions (user_id, level_id, player_name) VALUES (1, :a, 'Nikiktos')"
        ), {"a": pos5})
        conn.execute(text(
            "INSERT INTO level_completions (user_id, level_id, player_name) VALUES (1, :b, 'nikiktos')"
        ), {"b": pos8})
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, username, level_name, status, submitted_at) "
            "VALUES (1, 1, 'nikiktos', 'Acid factory', 'approved', '2026-09-01 10:00:00')"
        ))

    players = c.get("/api/gd/players").get_json()
    names = [p["player_name"] for p in players]
    assert names == ["Nikiktos"]
    top = players[0]
    assert top["points"] == 1500 and top["total_approved"] == 2
    assert top["demons_count"] == 0

    # Level completions list dedupes the same persona across case variants.
    d = c.get(f"/api/gd/level/{pos8}/completions").get_json()
    completers = [u["player_name"] for u in d["completions"]]
    assert completers == ["nikiktos"]


@patch("api.index.get_db_engine")
def test_gd_admin_completion_add_remove(mock_engine):
    """Admin marks a level as completed (with media) and can remove it again."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    client = app.test_client()

    reg = client.post("/api/auth/register", json={
        "login": "boss", "password": "secret123", "email": "boss@test.local",
    })
    reg_data = reg.get_json()
    _promote_admin(reg_data["user_id"])
    headers = _auth_headers(reg_data["token"])

    preg = client.post("/api/auth/register", json={
        "login": "luke", "password": "secret123", "email": "luke@test.local",
    })
    player_id = preg.get_json()["user_id"]
    with engine.begin() as conn:
        conn.execute(text("UPDATE web_users SET gd_nickname = 'LucasTeam' WHERE id = :i"), {"i": player_id})

    level_id = index_api.add_gd_level("Supersonic", 1, "Unknown")
    assert level_id is not None

    # Non-admin cannot add.
    r = client.post("/api/gd/admin/player/LucasTeam/completions",
                    data={"level_id": level_id, "media_url": "https://youtu.be/x"})
    assert r.status_code == 403

    # Media is required.
    r = client.post("/api/gd/admin/player/LucasTeam/completions",
                    data={"level_id": level_id}, headers=headers)
    assert r.status_code == 400

    # Admin adds with a media link.
    r = client.post("/api/gd/admin/player/LucasTeam/completions",
                    data={"level_id": level_id, "media_url": "https://youtu.be/12345"},
                    headers=headers)
    assert r.status_code == 200
    prof = r.get_json()["profile"]
    assert prof["found"] is True and prof["player_name"] == "LucasTeam"
    assert prof["completions_count"] == 1 and prof["points"] == 1000

    sub = engine.connect().execute(text(
        "SELECT status, username, media_type, level_name FROM submissions ORDER BY id DESC LIMIT 1"
    )).mappings().first()
    assert sub["status"] == "approved" and sub["username"] == "LucasTeam"
    assert sub["media_type"] == "link" and sub["level_name"] == "Supersonic"

    # A level already completed is not added twice.
    r = client.post("/api/gd/admin/player/LucasTeam/completions",
                    data={"level_id": level_id, "media_url": "https://youtu.be/12345"},
                    headers=headers)
    assert r.status_code == 400

    # Player now appears in the roster as its own persona.
    players = client.get("/api/gd/players").get_json()
    by_nick = {p["player_name"]: p for p in players}
    assert by_nick["LucasTeam"]["points"] == 1000 and by_nick["LucasTeam"]["demons_count"] == 0

    # Admin removes the level from the completed list.
    r = client.delete(f"/api/gd/admin/player/LucasTeam/completions?level_id={level_id}", headers=headers)
    assert r.status_code == 200
    prof = r.get_json()["profile"]
    assert prof["found"] is True and prof["completions_count"] == 0 and prof["points"] == 0
    players_after = client.get("/api/gd/players").get_json()
    assert all(p["player_name"] != "LucasTeam" for p in players_after)


@patch("api.index.get_db_engine")
def test_gd_admin_rename_persona(mock_engine):
    """Admin renames a GD persona (merges), non-admins can't, page hides admin JS for them."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    client = app.test_client()
    _AI_RATE_LIMITS.clear()

    reg = client.post("/api/auth/register", json={
        "login": "boss", "password": "secret123", "email": "boss@test.local",
    })
    reg_data = reg.get_json()
    _promote_admin(reg_data["user_id"])
    headers = _auth_headers(reg_data["token"])

    def _mk_player(login, gd_nick):
        r = client.post("/api/auth/register", json={
            "login": login, "password": "secret123", "email": f"{login}@test.local",
        })
        uid = r.get_json()["user_id"]
        with engine.begin() as conn:
            conn.execute(text("UPDATE web_users SET gd_nickname = :g WHERE id = :i"), {"g": gd_nick, "i": uid})

    _mk_player("luke", "LucasTeam")
    _mk_player("luke2", "LucasTeam12321")

    sup = index_api.add_gd_level("Supersonic", 1, "Unknown")
    grey = index_api.add_gd_level("Grey Trap", 3, "Unknown")
    assert sup is not None and grey is not None

    def _add(nick, lid):
        return client.post("/api/gd/admin/player/" + nick + "/completions",
                           data={"level_id": lid, "media_url": f"https://youtu.be/{lid}"},
                           headers=headers)

    assert _add("LucasTeam", sup).status_code == 200
    assert _add("LucasTeam12321", grey).status_code == 200

    # Non-admin cannot rename.
    reg = client.post("/api/auth/register", json={"login": "bob", "password": "secret123", "email": "bob@test.local"})
    bob_token = reg.get_json()["token"]
    r = client.put("/api/gd/admin/player/LucasTeam/nick", data={"new_nick": "X"}, headers=_auth_headers(bob_token))
    assert r.status_code == 403

    # Anonymous page has no admin flag; admin page gets it server-side.
    anon_page = client.get("/gd/player/LucasTeam").get_data(as_text=True)
    assert "var IS_ADMIN = false;" in anon_page
    adm_page = client.get("/gd/player/LucasTeam", headers=headers).get_data(as_text=True)
    assert "var IS_ADMIN = true;" in adm_page

    # Rename merges the persona into the target nick.
    r = client.put("/api/gd/admin/player/LucasTeam/nick", data={"new_nick": "LucasTeam12321"}, headers=headers)
    assert r.status_code == 200
    prof = r.get_json()["profile"]
    assert prof["found"] is True and prof["player_name"] == "LucasTeam12321"
    assert prof["completions_count"] == 2 and prof["points"] == 1500

    players = client.get("/api/gd/players").get_json()
    by_nick = {p["player_name"]: p for p in players}
    assert by_nick["LucasTeam12321"]["points"] == 1500
    assert all(p["player_name"] != "LucasTeam" for p in players)

    # Old nick still resolves via the account fallback (the web user owns those completions).
    old = client.get("/api/gd/player/LucasTeam").get_json()
    assert old["found"] is True


@patch("api.index.get_db_engine")
def test_gd_admin_set_completion_media(mock_engine):
    """Admin can (re)attach media to an existing completion without re-adding it."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    client = app.test_client()
    _AI_RATE_LIMITS.clear()

    reg = client.post("/api/auth/register", json={"login": "boss", "password": "secret123", "email": "boss@test.local"})
    reg_data = reg.get_json()
    _promote_admin(reg_data["user_id"])
    headers = _auth_headers(reg_data["token"])

    lvl = index_api.add_gd_level("Acid Factory", 5, "Unknown")

    # Player with an existing completion (approved submission without media).
    reg2 = client.post("/api/auth/register", json={"login": "nikiktos", "password": "secret123", "email": "nikiktos@test.local"})
    with engine.begin() as conn:
        conn.execute(text("UPDATE web_users SET gd_nickname = 'Nikiktos' WHERE id = :i"),
                     {"i": reg2.get_json()["user_id"]})
    r = client.post("/api/gd/admin/player/nikiktos/completions",
                    data={"level_id": lvl, "media_url": "https://example.com/r1.mp4"},
                    headers=headers)
    assert r.status_code == 200
    assert r.get_json()["profile"]["completions_count"] == 1

    # Non-admin cannot change media.
    r = client.post(f"/api/gd/admin/player/nikiktos/level/{lvl}/media",
                    data={"media_url": "https://example.com/new.mp4"})
    assert r.status_code == 403

    # Media is required.
    r = client.post(f"/api/gd/admin/player/nikiktos/level/{lvl}/media", data={}, headers=headers)
    assert r.status_code == 400

    # Unknown level.
    r = client.post("/api/gd/admin/player/nikiktos/level/999/media",
                    data={"media_url": "https://example.com/x.mp4"}, headers=headers)
    assert r.status_code == 404

    # Admin replaces media with a photo link.
    r = client.post(f"/api/gd/admin/player/nikiktos/level/{lvl}/media",
                    data={"media_url": "https://example.com/ss.jpg"}, headers=headers)
    assert r.status_code == 200
    assert r.get_json()["media_type"] == "link"

    comps = client.get(f"/api/gd/level/{lvl}/completions").get_json()["completions"]
    row = next(x for x in comps if x["username"] == "nikiktos")
    assert row["media_file_id"] == "https://example.com/ss.jpg" and row["media_type"] == "link"

    # Level page embeds the media renderer.
    body = client.get(f"/gd/level/{lvl}").get_data(as_text=True)
    assert "gdMediaHtml" in body


@patch("api.index.get_db_engine")
def test_gd_first_completion_badge(mock_engine):
    """The earliest approved completion on a level is flagged as the first victor."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    engine = mock_engine.return_value
    c = app.test_client()

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO web_users (id, login, password_hash, display_name, gd_nickname) VALUES (1, 'alice', 'x', 'Alice', 'Riot')"
        ))
        conn.execute(text(
            "INSERT INTO users (id, telegram_id, first_name, username) VALUES (1, 777, 'Боб', 'bob_tg')"
        ))
    level_id = index_api.add_gd_level("Tartarus", 1, "Extreme Demon")
    assert level_id is not None

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, username, level_name, status, submitted_at) "
            "VALUES (1, 1, 'Riot', 'Tartarus', 'approved', '2026-01-01 10:00:00')"
        ))
        conn.execute(text(
            "INSERT INTO submissions (id, user_id, username, level_name, status, submitted_at) "
            "VALUES (2, 777, 'TgBeast', 'Tartarus', 'approved', '2026-01-02 10:00:00')"
        ))

    resp = c.get(f"/api/gd/level/{level_id}/completions")
    assert resp.status_code == 200
    d = resp.get_json()
    by_name = {u["player_name"]: u for u in d["completions"]}
    assert "Riot" in by_name and "TgBeast" in by_name
    assert by_name["Riot"]["is_first"] is True
    assert by_name["TgBeast"]["is_first"] is False


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


@patch("api.index.get_db_engine")
def test_trivia_question_and_answer(mock_engine):
    """Trivia session flow: ask a question, answer it, verify result."""
    from api import index as index_api
    mock_engine.return_value = _make_engine()
    _TRIVIA_SESSIONS.clear()
    client = app.test_client()
    reg = client.post("/api/auth/register", json={
        "login": "trivia", "password": "secret123", "email": "trivia@test.local",
    })
    headers = _auth_headers(reg.get_json()["token"])
    q = client.post("/api/trivia/question").get_json()
    assert "id" in q
    assert "session_id" in q
    assert len(q["options"]) == 4
    assert "correct_index" not in q, "correct_index must not leak to client"
    # Freemium 67/33: the answer (and coin award) is only for signed-in users.
    anon = client.post("/api/trivia/answer", json={"session_id": q["session_id"], "answer_index": 0})
    assert anon.status_code == 401
    assert anon.get_json().get("auth_required") is True
    first = client.post("/api/trivia/answer", json={"session_id": q["session_id"], "answer_index": 0},
                        headers=headers).get_json()
    assert "correct" in first
    assert "explanation" in first
    assert "correct_text" in first
    stale = client.post("/api/trivia/answer", json={"session_id": 99999, "answer_index": 0},
                        headers=headers).get_json()
    assert stale["correct"] is False


def test_trivia_manual_distractors_realistic():
    """Manual-distractor questions keep options unique within one round."""
    client = app.test_client()
    for _ in range(30):
        q = client.post("/api/trivia/question").get_json()
        assert "correct_index" not in q, "correct_index must not leak"
        assert len(set(q["options"])) == 4


@patch("api.index.get_db_engine")
def test_auth_register_login_me_logout(mock_engine):
    """Full auth lifecycle with a real in-memory DB."""
    mock_engine.return_value = _make_engine()
    client = app.test_client()

    r = client.post("/api/auth/register", json={"login": "us", "password": "short"})
    assert r.status_code == 400

    r = client.post("/api/auth/register", json={"login": "alice", "password": "secret123", "email": "alice@test.local"})
    assert r.status_code == 200
    body = r.get_json()
    assert "token" in body
    token = body["token"]

    dup = client.post("/api/auth/register", json={"login": "alice", "password": "secret123", "email": "alice_dup@test.local"})
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
        "login": "boss", "password": "secret123", "email": "boss@test.local",
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

    reg2 = client.post("/api/auth/register", json={"login": "bob", "password": "secret123", "email": "bob@test.local"})
    token2 = reg2.get_json()["token"]
    lst2 = client.get("/api/admin/feedback", headers=_auth_headers(token2))
    assert lst2.status_code == 403


@patch("api.index.get_db_engine")
def test_admin_stats_and_users(mock_engine):
    """Admin endpoints return aggregated data for an admin session."""
    mock_engine.return_value = _make_engine()
    client = app.test_client()

    reg = client.post("/api/auth/register", json={
        "login": "root", "password": "secret123", "email": "root@test.local",
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


@patch("api.index.get_db_engine")
def test_admin_delete_user(mock_engine):
    """DELETE /api/admin/users/<id> удаляет аккаунт вместе с зависимыми данными."""
    engine = _make_engine()
    mock_engine.return_value = engine
    client = app.test_client()

    admin = client.post("/api/auth/register", json={
        "login": "boss", "password": "secret123", "email": "boss@test.local",
    }).get_json()
    _promote_admin(admin["user_id"])
    admin_headers = _auth_headers(admin["token"])

    target = client.post("/api/auth/register", json={
        "login": "smoke_x", "password": "secret123", "email": "smoke_x@test.local",
    }).get_json()
    target_id = target["user_id"]

    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO web_activity_log (user_id, day, module, actions) "
            "VALUES (:uid, '2026-01-01', 'code', 3)"), {"uid": target_id})
        conn.execute(text(
            "INSERT INTO web_friends (user_id, friend_id) VALUES (:a, :b), (:b, :a)"),
            {"a": target_id, "b": admin["user_id"]})
        conn.execute(text(
            "INSERT INTO friend_requests (from_user, to_user) VALUES (:a, :b)"),
            {"a": target_id, "b": admin["user_id"]})
        conn.execute(text(
            "INSERT INTO web_feedback (user_id, login, category, message) "
            "VALUES (:uid, 'smoke_x', 'bug', 'test')"), {"uid": target_id})

    assert client.get("/api/auth/me", headers=_auth_headers(target["token"])).status_code == 200

    resp = client.delete(f"/api/admin/users/{target_id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["login"] == "smoke_x"
    assert data["removed"]

    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM web_users WHERE id = :i"),
                            {"i": target_id}).scalar() == 0
        checks = {
            "web_activity_log": "user_id = :i",
            "web_friends": "user_id = :i OR friend_id = :i",
            "friend_requests": "from_user = :i OR to_user = :i",
            "web_feedback": "user_id = :i",
        }
        for table, where in checks.items():
            left = conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"),
                                {"i": target_id}).scalar()
            assert left == 0, f"{table} not cleaned: {left}"
        for table, where in (("web_friends", "user_id = :i OR friend_id = :i"),
                             ("friend_requests", "from_user = :i OR to_user = :i")):
            left = conn.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"),
                                {"i": admin["user_id"]}).scalar()
            assert left == 0, f"{table} has dangling rows for admin: {left}"

    assert client.get("/api/auth/me", headers=_auth_headers(target["token"])).status_code == 401
    assert client.delete(f"/api/admin/users/{target_id}", headers=admin_headers).status_code == 404
    assert client.delete(f"/api/admin/users/{admin['user_id']}", headers=admin_headers).status_code == 400
    assert client.delete(f"/api/admin/users/{target_id}").status_code == 403


def test_reading_trainer_page_clean_html():
    """Reading trainer page has no stray f-string artifacts."""
    body = app.test_client().get("/reading_trainer.html").get_data(as_text=True)
    assert re.search(r"id=\"stats-bar\"", body)


def test_suggest_page_contains_form():
    """The /suggest page contains the feedback form fields."""
    body = app.test_client().get("/suggest").get_data(as_text=True)
    assert "category" in body
    assert "module" in body


def test_register_rate_limits():
    """Регистрация с одного IP: burst 30/5мин — школьный класс за NAT регистрируется;
    жёсткий суточный лимит (DB-backed) блокирует ботов."""
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()

        from api.index import _REGISTER_BURST, _REGISTER_DAILY

        for i in range(_REGISTER_BURST):
            r = client.post("/api/auth/register",
                            json={"login": f"stu{i:02d}", "password": "secret123",
                                  "email": f"stu{i:02d}@t.local"})
            assert r.status_code == 200, (i, r.get_json())

        r = client.post("/api/auth/register", json={"login": "spam", "password": "secret123"})
        assert r.status_code == 429

    # суточный лимит: rate_limits заполнена → 429 даже с чистым burst-счётчиком
    _AI_RATE_LIMITS.clear()  # сбросить in-memory burst от 30 регистраций выше
    engine = _make_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS rate_limits "
            "(key TEXT NOT NULL, ts DOUBLE PRECISION NOT NULL)"))
        for _ in range(_REGISTER_DAILY):
            conn.execute(text(
                "INSERT INTO rate_limits (key, ts) VALUES ('reg_day:127.0.0.1', :ts)"),
                {"ts": time.time()})
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        r = client.post("/api/auth/register", json={"login": "spam2", "password": "secret123"})
        assert r.status_code == 429
        assert "сутки" in (r.get_json().get("error") or "")


def test_dnd_start_creates_schema_on_fresh_db():
    """Regression: "Новая сессия" must work on a cold DB, not only with a warm schema.

    ``_ensure_dnd_tables`` used raw PostgreSQL DDL (SERIAL / TIMESTAMPTZ / NOW() and a
    single multi-column ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS``) that SQLite
    rejects, so the whole function aborted, ``dnd_sessions`` never got ``share_code``
    and ``POST /api/dnd/start`` answered 500. Unlike ``test_dnd_session_sharing_flow``
    this drives the real runtime instead of mocking ``cmd_dnd_start``.
    """
    from api.index import _ensure_dnd_tables

    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        _ensure_dnd_tables(engine)
        client = app.test_client()
        reg = client.post("/api/auth/register", json={
            "login": "dndreal", "password": "secret123", "email": "dndreal@test.local",
        })
        headers = _auth_headers(reg.get_json()["token"])

        r = client.post("/api/dnd/start", json={"name": "Подземелье"}, headers=headers)
        assert r.status_code == 200, r.get_data(as_text=True)[:400]
        d = r.get_json()
        assert d["ok"] is True
        assert d["active"] is True
        assert d["share_code"]
        assert d["share_url"] == "/dnd?session=" + d["share_code"]

        # Re-running the DDL on an already-initialised DB must stay a no-op.
        _ensure_dnd_tables(engine)
        with engine.connect() as conn:
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(dnd_sessions)"))}
        assert "share_code" in cols
        assert "chapter_breakdown" in cols


@patch("api.index.get_db_engine")
def test_admin_only_routes_reject_anonymous(mock_engine):
    """Diagnostics must not be reachable without an admin session.

    Regression for the P0 audit: /api/set_webhook leaked WEBHOOK_SECRET in its
    response body and let anyone repoint the bot's webhook, /api/debug_webhook,
    /api/test_telegram and /debug_puzzle were fully public, and
    /test_puzzle/<user_id> returned another user's coin balance (IDOR).
    """
    mock_engine.return_value = _make_engine()
    client = app.test_client()

    admin_only = [
        ("get", "/api/set_webhook"),
        ("get", "/api/debug_webhook"),
        ("get", "/api/test_telegram"),
        ("get", "/debug_puzzle"),
        ("get", "/test_puzzle/1"),
        ("get", "/test_send/123"),
    ]
    for method, path in admin_only:
        resp = getattr(client, method)(path)
        assert resp.status_code == 403, f"{path} должен требовать админа, got {resp.status_code}"
        assert "прав" in (resp.get_json().get("error") or "").lower()

    reg = client.post("/api/auth/register", json={
        "login": "plainuser", "password": "secret123", "email": "plain@test.local",
    })
    headers = _auth_headers(reg.get_json()["token"])
    assert client.get("/api/set_webhook", headers=headers).status_code == 403
    assert client.get("/test_puzzle/1", headers=headers).status_code == 403

    _promote_admin(reg.get_json()["user_id"])
    monkey = pytest.MonkeyPatch()
    monkey.setenv("WEBHOOK_SECRET", "s3cr3t-webhook-value")
    try:
        vh = {"Host": "bank-bot-ruby.vercel.app"}
        vh.update(headers)
        with patch("api.index.requests.get") as mock_get:
            mock_get.return_value = Mock(ok=True)
            mock_get.return_value.json.return_value = {"ok": True, "result": True, "description": "ok"}
            r = client.get("/api/set_webhook", headers=vh)
    finally:
        monkey.undo()
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    body = r.get_json()
    assert "***" in body["url"], "секрет не должен попадать в ответ"
    assert "s3cr3t-webhook-value" not in r.get_data(as_text=True)


@patch("api.index.get_db_engine")
def test_endings_process_requires_auth_and_caps_text(mock_engine):
    """/api/endings_process is an LLM call: gate it and cap the payload."""
    mock_engine.return_value = _make_engine()
    client = app.test_client()

    anon = client.post("/api/endings_process", json={"text": "Мама мыла раму."})
    assert anon.status_code == 401
    assert anon.get_json().get("auth_required") is True

    reg = client.post("/api/auth/register", json={
        "login": "endings", "password": "secret123", "email": "endings@test.local",
    })
    headers = _auth_headers(reg.get_json()["token"])

    too_long = client.post("/api/endings_process", json={"text": "абвгд " * 5000}, headers=headers)
    assert too_long.status_code == 400
    assert "длинный" in (too_long.get_json().get("error") or "")

    with patch("api.index.call_ai_api", return_value=(
        '[{"t":"Мама "},{"b":"мыл","e":"а"},{"t":" "},{"b":"рам","e":"у"},{"t":"."}]'
    )):
        r = client.post("/api/endings_process", json={"text": "Мама мыла раму."}, headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("segments")


@patch("api.index.get_db_engine")
def test_music_upload_endpoints_require_auth(mock_engine):
    """/api/music/analyze|change_tempo|change_key are CPU-heavy: require a session."""
    mock_engine.return_value = _make_engine()
    client = app.test_client()

    for path in ("/api/music/analyze", "/api/music/change_tempo", "/api/music/change_key"):
        resp = client.post(path, data={})
        assert resp.status_code == 401, f"{path}: {resp.status_code}"
        assert resp.get_json().get("auth_required") is True


@patch("api.index.get_db_engine")
def test_verb_generation_cooldown_not_bypassable_by_user_id(mock_engine):
    """The generation cooldown must not be keyed on a client-supplied user_id."""
    from api.index import (
        VERB_GEN_LOCK,
        _VERB_GEN_COOLDOWN,
        _VERB_GEN_LOCK_MAX,
        _verb_gen_locked,
    )

    mock_engine.return_value = _make_engine()
    VERB_GEN_LOCK.clear()
    client = app.test_client()

    calls = []

    def _fake_gen(verbs, count, mode, wishes):
        calls.append(verbs)
        return [{"inf": "делать", "past": "делал", "pp": "делал"}]

    with patch("api.index._generate_verb_exercise", side_effect=_fake_gen), \
         patch("api.index._save_verb_exercise"), \
         patch("api.index._load_verb_exercise", return_value=None):
        first = client.post("/api/verbs/generate", json={"verbs": "делать", "user_id": "u1"})
        assert first.status_code == 200, first.get_data(as_text=True)[:200]
        second = client.post("/api/verbs/generate", json={"verbs": "делать", "user_id": "u2"})
        assert second.status_code == 429, "обход кулдауна сменой user_id"

    assert len(calls) == 1
    assert _VERB_GEN_COOLDOWN == 10

    for n in range(_VERB_GEN_LOCK_MAX + 10):
        VERB_GEN_LOCK[f"filler{n}"] = 0.0
    _verb_gen_locked("probe", time.time())
    assert len(VERB_GEN_LOCK) <= _VERB_GEN_LOCK_MAX, "словарь кулдауна должен чиститься"
    VERB_GEN_LOCK.clear()


def _iter_inline_scripts(html: str):
    """Yield (index, source) for every inline <script> block in rendered HTML."""
    for n, m in enumerate(re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)):
        if m.strip():
            yield n, m


def test_rendered_pages_have_no_js_syntax_errors():
    """Every inline script on a rendered page must survive ``node --check``.

    The bug this guards is silent: the page is a Python string, so ``\\n`` and
    ``\\'`` are consumed by Python before the browser ever sees the JS. That broke
    /chess and /endings_trainer.html completely (both died with a SyntaxError in
    the middle of the page script) while every other test still passed. Checking
    the *rendered* HTML is the only place the damage is visible.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node не установлен — нельзя проверить синтаксис JS")

    # Страницы с самым большим объёмом inline-JS плюс обе ранее сломанные.
    paths = [
        "/chess",
        "/endings_trainer.html",
        "/dnd",
        "/math",
        "/physics",
        "/reading_trainer",
        "/irregular_verbs",
        "/trivia",
    ]
    client = app.test_client()
    checked = 0
    for path in paths:
        resp = client.get(path)
        if resp.status_code != 200:
            continue
        html = resp.get_data(as_text=True)
        for idx, block in _iter_inline_scripts(html):
            with tempfile.NamedTemporaryFile(
                "w", suffix=".js", delete=False, encoding="utf-8"
            ) as fh:
                fh.write(block)
                tmp = fh.name
            try:
                proc = subprocess.run(
                    [node, "--check", tmp], capture_output=True, text=True
                )
            finally:
                os.unlink(tmp)
            assert proc.returncode == 0, (
                f"{path}: inline script #{idx} не парсится node\n{proc.stderr[:500]}"
            )
            checked += 1
    assert checked > 0, "не нашлось ни одного inline-скрипта для проверки"
