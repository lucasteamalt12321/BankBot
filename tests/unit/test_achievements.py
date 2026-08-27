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
            CREATE TABLE web_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text("""
            CREATE TABLE emperors_progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                card_key TEXT NOT NULL,
                reps INTEGER NOT NULL DEFAULT 0,
                interval_days INTEGER NOT NULL DEFAULT 0,
                ease REAL NOT NULL DEFAULT 2.5,
                due REAL NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                counter INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_emperors_progress_user ON emperors_progress(user_id)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_emperors_progress_user_card ON emperors_progress(user_id, card_key)"))
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
        detail = {u["code"]: u for u in data["unlocked_detail"]}
        assert detail["first_step"]["name"]
        assert detail["first_step"]["icon"]
        assert detail["first_step"]["code"] == "first_step"

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
        assert data["total_count"] >= 200
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


def test_oge_study_achievements_unlock():
    from api.index import app, _web_user_id

    engine = _make_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE study_progress (
                user_id INTEGER NOT NULL,
                module TEXT NOT NULL,
                card_key TEXT NOT NULL,
                reps INTEGER NOT NULL DEFAULT 0,
                interval_days REAL NOT NULL DEFAULT 0,
                ease REAL NOT NULL DEFAULT 2.5,
                due REAL NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                counter INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                created_at REAL NOT NULL DEFAULT 0,
                last_correct_at REAL NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX uq_sp ON study_progress(user_id, module, card_key)"))
        suid = _web_user_id("u42")
        # 6 mastered math cards (streak>=3, 5 correct each) -> answers 30, mastered 6
        for i in range(6):
            conn.execute(text(
                "INSERT INTO study_progress (user_id, module, card_key, reps, streak,"
                " correct_count, wrong_count, counter, updated_at)"
                " VALUES (:s, 'math', :k, 4, 4, 5, 0, 5, 1)"
            ), {"s": suid, "k": f"formula::f{i}"})
        # 8 physics cards, 1 correct each, not mastered -> answers 8, mastered 0
        for i in range(8):
            conn.execute(text(
                "INSERT INTO study_progress (user_id, module, card_key, reps, streak,"
                " correct_count, wrong_count, counter, updated_at)"
                " VALUES (:s, 'physics', :k, 1, 0, 1, 0, 1, 1)"
            ), {"s": suid, "k": f"task::t{i}"})
    c, auth, p, p2, p3 = _register(engine)
    with p, p2, p3:
        # trigger _check_web_achievements (reads seeded study_progress facts)
        r = c.post("/api/achievements/activity", headers=auth, json={"module": "math"})
        assert r.status_code == 200
        unlocked = set(r.get_json()["unlocked"])
        assert "math_first" in unlocked
        assert "math_25" in unlocked
        assert "math_mastered_5" in unlocked
        assert "math_mastered_10" not in unlocked
        assert "physics_first" in unlocked
        assert "physics_25" not in unlocked
        assert "physics_mastered_all" not in unlocked
        assert "history_first" not in unlocked

        conf = c.get("/api/achievements", headers=auth).get_json()
        ach = {a["code"]: a for a in conf["achievements"]}
        assert ach["math_first"]["unlocked"] is True
        assert ach["math_25"]["unlocked"] is True
        assert ach["math_mastered_5"]["unlocked"] is True
        assert ach["math_mastered_10"]["unlocked"] is False
        assert ach["physics_first"]["unlocked"] is True
        assert ach["physics_25"]["unlocked"] is False
        assert ach["physics_mastered_all"]["unlocked"] is False
        assert ach["history_first"]["unlocked"] is False


def test_general_stats_endpoint():
    from api.index import app

    engine = _make_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE study_progress (
                user_id INTEGER NOT NULL,
                module TEXT NOT NULL,
                card_key TEXT NOT NULL,
                reps INTEGER NOT NULL DEFAULT 0,
                interval_days REAL NOT NULL DEFAULT 0,
                ease REAL NOT NULL DEFAULT 2.5,
                due REAL NOT NULL DEFAULT 0,
                streak INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                counter INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                created_at REAL NOT NULL DEFAULT 0,
                last_correct_at REAL NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX uq_sp2 ON study_progress(user_id, module, card_key)"))

    c, auth, p, p2, p3 = _register(engine)
    anon = c.get("/api/stats")
    assert anon.status_code == 401
    with p, p2, p3:
        for mod, n in (("canon", 3), ("chess", 5), ("math", 2), ("gd", 1)):
            for _ in range(n):
                r = c.post("/api/achievements/activity", headers=auth, json={"module": mod})
                assert r.status_code == 200

        d = c.get("/api/stats", headers=auth).get_json()
        assert d["ok"] is True
        assert d["streak"]["current"] >= 1
        assert d["totals"]["actions"] == 3 + 5 + 2 + 1
        assert d["totals"]["active_days"] == 1
        # modules is an ordered LIST (Flask sort_keys Alphabetizes dict keys,
        # so order is preserved only in a list)
        mods = {m["key"]: m for m in d["modules"]}
        assert mods["canon"]["label"] == "Канон"
        assert mods["canon"]["actions"] == 3
        assert mods["chess"]["actions"] == 5
        # sorted by actions desc -> chess first (list preserves order)
        assert d["modules"][0]["actions"] == 5
        assert d["modules"][0]["emoji"] == "♟️"
        # OGE block present (empty study_progress -> modules key exists)
        assert isinstance(d["oge"], dict)
        assert "modules" in d["oge"]
        assert "overall_readiness" in d["oge"]
