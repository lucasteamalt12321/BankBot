"""Freemium-гейтинг 67/33 (FRE-02/06/07) — 401 {auth_required} для гейтов,
регистрация без email + бонус 100 монет + created_via.

API-тесты сидят на in-memory StaticPool-движке (паттерн test_achievements):
реальный get_db_engine в этой среде через log_error уходит в Telegram-запрос.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from api.index import app


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    raw = engine.raw_connection()
    raw.create_function("NOW", 0, lambda: datetime.now(timezone.utc).isoformat())
    raw.close()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE web_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login VARCHAR(64) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(100),
                gd_nickname VARCHAR(64),
                telegram_id BIGINT,
                lichess_nickname VARCHAR(64),
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ,
                email VARCHAR(255) UNIQUE,
                created_via VARCHAR(32)
            )
        """))
        conn.execute(text("""
            CREATE TABLE web_sessions (
                token VARCHAR(64) PRIMARY KEY,
                user_id INTEGER,
                created_at TIMESTAMPTZ
            )
        """))
        conn.execute(text("""
            CREATE TABLE user_coins (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                last_puzzle_at TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE web_coin_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                description VARCHAR(255)
            )
        """))
    return engine


_FIX = {"engine": None, "token": None, "user_id": None, "login": None}


def _fixture():
    """Один движок + один зарегистрированный пользователь на процесс pytest."""
    if _FIX["token"]:
        return _FIX["engine"], _FIX["token"]
    engine = _make_engine()
    login = "freemium" + uuid.uuid4().hex[:8]
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        resp = client.post(
            "/api/auth/register",
            json={
                "login": login,
                "password": "secret1",
                "display_name": "Freemium Test",
                "source": "unit-test-register",
            },
        )
        data = resp.get_json() or {}
        assert resp.status_code == 200, data
        _FIX["engine"] = engine
        _FIX["token"] = data["token"]
        _FIX["user_id"] = data["user_id"]
        _FIX["login"] = login
    return engine, data["token"]


def _patch_db(engine):
    return patch("api.index.get_db_engine", return_value=engine)


# ── FRE-07: регистрация без email + бонус 100 монет + created_via ──────────


def test_register_without_email_works_and_awards_bonus():
    from api.index import get_user_coins, _web_user_id
    from sqlalchemy import select

    engine, _ = _fixture()
    with _patch_db(engine):
        coins = get_user_coins(_web_user_id("u" + str(_FIX["user_id"])))
        assert int((coins or {}).get("balance", 0)) == 100

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT created_via, email FROM web_users WHERE login = :l"),
                {"l": _FIX["login"]},
            ).mappings().first()
        assert row["created_via"] == "unit-test-register"
        assert row["email"] is None

        with engine.connect() as conn:
            log = conn.execute(
                select(text("amount")).select_from(text("web_coin_log"))
            ).mappings().all()
        assert any(int(r["amount"]) == 100 for r in log)


# ── FRE-02/06: гейты возвращают единый 401 {auth_required:true} без токена ──


GATED_CASES = [
    ("post", "/api/dnd/stop", {}),
    ("post", "/api/dnd/fix", {}),
    ("post", "/api/chess/link", {}),
    ("post", "/api/md2pdf/format", {"text": "# hi"}),
    ("post", "/api/music/overlay", {}),
    ("get", "/api/study/ai-plan", {}),
    ("post", "/api/study/plan", {}),
    ("post", "/api/study/chat", {}),
    ("get", "/api/study/hint?module=math", {}),
    ("get", "/api/study/stats", {}),
    ("get", "/api/chess/stats", {}),
    ("post", "/api/exam/ai-record", {}),
    ("post", "/api/verbs/submit", {}),
    ("post", "/api/trivia/answer", {}),
]


def test_gated_endpoints_require_auth():
    engine, _ = _fixture()
    client = app.test_client()
    with _patch_db(engine):
        for method, url, payload in GATED_CASES:
            f = getattr(client, method)
            resp = f(url, json=payload) if method == "post" else f(url)
            body = resp.get_json() or {}
            assert resp.status_code == 401, (url, resp.status_code)
            assert body.get("auth_required") is True, url


def test_gates_pass_with_valid_token():
    engine, token = _fixture()
    client = app.test_client()
    headers = {"X-Auth-Token": token}
    with _patch_db(engine):
        # Авторизация пройдена → дальше бизнес-проверка (без обращения к отсутствующим
        # таблицам и без путь до log_error → telegram).
        r1 = client.post("/api/md2pdf/format", json={"text": "   "}, headers=headers)
        assert r1.status_code == 400  # прошёл гейт, текст пуст

        r2 = client.post("/api/music/overlay", data={}, headers=headers)
        assert r2.status_code == 400  # прошёл гейт, нет файлов

        r3 = client.post("/api/verbs/submit", json={}, headers=headers)
        assert r3.status_code == 404 or r3.status_code == 400  # не 401


# ── База остаётся открытой анонимам ─────────────────────────────────────────


def test_base_study_endpoints_free_for_anon():
    engine, _ = _fixture()
    client = app.test_client()
    with _patch_db(engine):
        r = client.get("/api/study/today")
        assert r.status_code == 200

        r = client.get("/api/study/recommendations")
        assert r.status_code == 200
        assert "subjects" in r.get_json()

        r = client.get("/api/study/progress")
        assert r.status_code == 200

        r = client.get("/api/study/chat")
        assert r.status_code == 200

        r = client.get("/api/study/due-cards")
        assert r.status_code == 200


def test_hint_banner_script_injected_into_subject_pages():
    """Глобальный патч fetch и модалка входа присутствуют на HTML-страницах."""
    client = app.test_client()
    resp = client.get("/math")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "ltGateInstalled" in body
    assert "showLtLogin" in body
    assert "/register?redirect=" in body