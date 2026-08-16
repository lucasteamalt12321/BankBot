"""Unit tests for the unified achievements & streak system (api.index)."""

from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE web_streak (
                user_id INTEGER PRIMARY KEY,
                last_active_day TEXT NOT NULL,
                current_streak INTEGER NOT NULL DEFAULT 0,
                longest_streak INTEGER NOT NULL DEFAULT 0,
                total_active_days INTEGER NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text("""
            CREATE TABLE web_activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                module TEXT NOT NULL,
                actions INTEGER NOT NULL DEFAULT 1
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX uq_web_activity_user_day_module ON web_activity_log(user_id, day, module)"))
        conn.execute(text("""
            CREATE TABLE web_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                unlocked_at REAL NOT NULL
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX uq_web_achievements_user_code ON web_achievements(user_id, code)"))
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
                description TEXT
            )
        """))
    return engine


def _register(engine):
    from api.index import app

    c = app.test_client()
    auth = {"X-Auth-Token": "test-token"}
    p = patch("api.index.get_db_engine", return_value=engine)
    p2 = patch("api.index._get_session_user", return_value={"id": 42, "login": "test"})
    p3 = patch("api.index._auth_token_from_request", return_value="test-token")
    return c, auth, p, p2, p3


def test_achievement_registry_count_and_shape():
    from api.index import ACHIEVEMENTS

    assert len(ACHIEVEMENTS) >= 100, "registry should hold ~100 achievements"
    seen = set()
    for code, a in ACHIEVEMENTS.items():
        assert code not in seen
        seen.add(code)
        assert a["icon"]
        assert a["name"]
        assert a["desc"]
        assert a["module"]
        assert a["weight"] == 10


def test_achievements_page_renders():
    from api.index import app

    c = app.test_client()
    resp = c.get("/achievements")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Достижения" in body
    assert "серия" in body
    assert "renderCalendar" in body


def test_activity_requires_auth():
    from api.index import app

    c = app.test_client()
    r = c.post("/api/achievements/activity", json={"module": "trivia"})
    assert r.status_code == 401
    r2 = c.get("/api/achievements")
    assert r2.status_code == 401


def test_activity_records_streak_and_unlocks_first():
    from api.index import app

    engine = _make_engine()
    c, auth, p, p2, p3 = _register(engine)
    with p, p2, p3:
        r = c.post("/api/achievements/activity", headers=auth, json={"module": "trivia", "actions": 1})
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["streak"]["current"] == 1
        assert data["streak"]["total_days"] == 1
        unlocked = set(data["unlocked"])
        assert "first_step" in unlocked
        assert "trivia_first" in unlocked
        assert "first_quiz" in unlocked
        assert "first_streak" not in unlocked

        # same day -> streak unchanged
        r2 = c.post("/api/achievements/activity", headers=auth, json={"module": "chess", "actions": 1})
        d2 = r2.get_json()
        assert d2["streak"]["current"] == 1
        assert d2["streak"]["total_days"] == 1

    # streak across days via patched day string
    engine2 = _make_engine()
    c2, auth2, p4, p5, p6 = _register(engine2)
    with p4, p5, p6, patch("api.index._day_str", side_effect=["2026-01-01", "2026-01-02"]):
        r3 = c2.post("/api/achievements/activity", headers=auth2, json={"module": "trivia"})
        assert r3.get_json()["streak"]["current"] == 1
        r4 = c2.post("/api/achievements/activity", headers=auth2, json={"module": "trivia"})
        d4 = r4.get_json()
        assert d4["streak"]["current"] == 2
        assert "first_streak" in set(d4["unlocked"])
        assert "streak_3" not in set(d4["unlocked"])


def test_achievements_list_endpoint():
    from api.index import app

    engine = _make_engine()
    c, auth, p, p2, p3 = _register(engine)
    with p, p2, p3:
        c.post("/api/achievements/activity", headers=auth, json={"module": "reading", "actions": 1})
        g = c.get("/api/achievements", headers=auth)
        data = g.get_json()
        assert data["total_count"] == 100
        assert data["unlocked_count"] >= 1
        assert data["streak"]["current"] == 1
        assert len(data["calendar"]) == 1
        ach = {a["code"]: a for a in data["achievements"]}
        assert ach["first_step"]["unlocked"] is True
        assert ach["streak_3"]["unlocked"] is False
        assert "reading" in data["modules"]


def test_achievements_page_has_calendar_and_filters():
    from api.index import app

    c = app.test_client()
    body = c.get("/achievements").get_data(as_text=True)
    assert "calendar" in body
    assert "streak" in body
    assert "module-filter" in body
    assert "achievements" in body