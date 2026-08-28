"""Unit tests for the unified OGE study progress core (table, API, recommendations)."""

import time
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
            CREATE TABLE study_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        conn.execute(text("CREATE UNIQUE INDEX uq_study_progress_user_module_card ON study_progress(user_id, module, card_key)"))
        conn.execute(text("""
            CREATE TABLE emperors_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    return engine


AUTH_HEADERS = {"X-Auth-Token": "test-token"}


def _auth_patches(engine):
    return (
        patch("api.index.get_db_engine", return_value=engine),
        patch("api.index._get_session_user", return_value={"id": 42, "login": "test"}),
        patch("api.index._auth_token_from_request", return_value="test-token"),
    )


def test_study_progress_save_get_reset_per_module():
    from api.index import app

    engine = _make_engine()
    c = app.test_client()
    p1, p2, p3 = _auth_patches(engine)
    with p1, p2, p3:
        resp = c.post("/api/study/progress", headers=AUTH_HEADERS, json={
            "module": "math",
            "cards": {"task::t1": {"reps": 2, "streak": 2, "correct": 2, "wrong": 0, "due": time.time() - 10}},
        })
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        resp = c.post("/api/study/progress", headers=AUTH_HEADERS, json={
            "module": "history",
            "cards": {"term::опричнина": {"reps": 1, "streak": 0, "correct": 1, "wrong": 2}},
        })
        assert resp.status_code == 200

        data = c.get("/api/study/progress", headers=AUTH_HEADERS).get_json()
        assert set(data["cards"].keys()) == {"math", "history"}
        assert data["cards"]["math"]["task::t1"]["reps"] == 2
        assert data["cards"]["history"]["term::опричнина"]["wrong"] == 2

        r = c.post("/api/study/progress", headers=AUTH_HEADERS, json={"module": "math", "reset": True})
        assert r.status_code == 200
        data = c.get("/api/study/progress", headers=AUTH_HEADERS).get_json()
        assert set(data["cards"].keys()) == {"history"}

    anon = c.get("/api/study/progress")
    assert anon.get_json() == {"cards": {}, "uid": 0}
    assert c.post("/api/study/progress", json={"module": "math", "cards": {}}).status_code == 401


def test_study_progress_unknown_module_rejected():
    from api.index import app

    engine = _make_engine()
    c = app.test_client()
    p1, p2, p3 = _auth_patches(engine)
    with p1, p2, p3:
        resp = c.post("/api/study/progress", headers=AUTH_HEADERS, json={"module": "hacking", "cards": {}})
        assert resp.status_code == 400


def test_recommendations_priorities_and_sorting():
    from api.index import app

    engine = _make_engine()
    c = app.test_client()
    p1, p2, p3 = _auth_patches(engine)
    with p1, p2, p3:
        c.post("/api/study/progress", headers=AUTH_HEADERS, json={
            "module": "history",
            "cards": {
                "event::a": {"reps": 3, "streak": 3, "correct": 3, "wrong": 0, "due": 1.0},
                "event::b": {"reps": 3, "streak": 3, "correct": 3, "wrong": 0, "due": 9999999999.0},
            },
        })
        c.post("/api/study/progress", headers=AUTH_HEADERS, json={
            "module": "informatics",
            "cards": {"lesson1_o1": {"reps": 0, "streak": 0, "correct": 0, "wrong": 3}},
        })
        data = c.get("/api/study/recommendations", headers=AUTH_HEADERS).get_json()

    subjects = data["subjects"]
    assert [s["module"] for s in subjects] and len(subjects) == 5
    scores = [s["score"] for s in subjects]
    assert scores == sorted(scores, reverse=True)

    by_mod = {s["module"]: s for s in subjects}
    hist = by_mod["history"]
    assert hist["due"] == 1
    assert hist["next_action"]["text"].startswith("Повторить")
    assert "?algo=flash" in hist["next_action"]["url"]

    info = by_mod["informatics"]
    assert info["weak"] == 1
    assert info["started"] == 1

    math_s = by_mod["math"]
    assert math_s["started"] == 0
    assert math_s["next_action"]["text"] == "Начать новую тему"

    anon = c.get("/api/study/recommendations")
    assert anon.get_json() == {"subjects": [], "uid": 0}


def test_migration_copies_emperors_rows_once():
    from api.index import _migrate_emperors_progress_to_study

    engine = _make_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO emperors_progress (user_id, card_key, reps, interval_days, ease, due, correct_count, wrong_count, counter, updated_at)
            VALUES (1, 'person::Пётр I', 4, 7, 2.5, 123.0, 4, 0, 4, 1000.0),
                   (1, 'event::Крестьянская война', 0, 0, 2.5, 0, 0, 1, -1, 1001.0)
        """))

    assert _migrate_emperors_progress_to_study(engine) is True
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT card_key, module, streak FROM study_progress ORDER BY card_key")).fetchall()
        assert len(rows) == 2
        assert all(r[1] == "history" for r in rows)
        by_key = {r[0]: r[2] for r in rows}
        assert by_key["person::Пётр I"] == 4

    assert _migrate_emperors_progress_to_study(engine) is False
    with engine.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(*) FROM study_progress")).scalar()
        assert cnt == 2


def test_ensure_creates_tables_on_empty_db():
    from api.index import _ensure_study_progress_tables

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _ensure_study_progress_tables(engine)
    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        assert "study_progress" in tables


def test_hub_contains_oge_plan_widget():
    from api.index import app

    c = app.test_client()
    body = c.get("/").get_data(as_text=True)
    assert 'id="oge-plan"' in body
    assert "loadOgePlan" in body
    assert "/api/study/recommendations" in body
    assert 'id="oge-mode-toggle"' in body
    assert "/api/study/plan" in body
    assert "cur-overlay" in body
    assert 'data-oge="1"' in body


def test_ai_plan_requires_auth():
    from api.index import app

    c = app.test_client()
    r = c.get("/api/study/ai-plan")
    assert r.status_code == 401


def test_ai_plan_generates_caches_and_forces():
    from unittest.mock import patch

    from api.index import _OGE_AI_PLAN_CACHE, app

    engine = _make_engine()
    c = app.test_client()
    p1, p2, p3 = _auth_patches(engine)
    with patch("api.index.call_ai_api", return_value="1. Математика — повторить формулы (20 мин).") as pai:
        with p1, p2, p3:
            _OGE_AI_PLAN_CACHE.clear()
            r = c.get("/api/study/ai-plan", headers=AUTH_HEADERS)
            assert r.status_code == 200
            d = r.get_json()
            assert d["ok"] is True and d["source"] == "ai" and "Математика" in d["plan"]
            assert pai.call_count == 1

            r2 = c.get("/api/study/ai-plan", headers=AUTH_HEADERS)
            assert r2.get_json()["source"] == "cache"
            assert pai.call_count == 1

            r3 = c.get("/api/study/ai-plan?force=1", headers=AUTH_HEADERS)
            assert r3.get_json()["source"] == "ai"
            assert pai.call_count == 2

    with p1, p2, p3:
        with patch("api.index.call_ai_api", return_value="❌ AI недоступен"):
            _OGE_AI_PLAN_CACHE.pop(next(iter(_OGE_AI_PLAN_CACHE)), None) if _OGE_AI_PLAN_CACHE else None
            r4 = c.get("/api/study/ai-plan?force=1", headers=AUTH_HEADERS)
            assert r4.status_code == 200
            d4 = r4.get_json()
            assert d4["ok"] is False and d4["source"] == "fallback" and d4["plan"] == ""


def test_stats_endpoint_returns_module_readiness():
    from api.index import app

    engine = _make_engine()
    c = app.test_client()
    p1, p2, p3 = _auth_patches(engine)
    with p1, p2, p3:
        c.post("/api/study/progress", headers=AUTH_HEADERS, json={
            "module": "math",
            "cards": {
                "task::t1": {"reps": 3, "streak": 3, "correct": 3, "wrong": 0,
                             "due": time.time() + 86400, "ts": time.time() * 1000},
            },
        })
        resp = c.get("/api/study/stats", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        d = resp.get_json()
        assert "modules" in d
        assert "overall_readiness" in d
        assert "streak" in d
        assert "today" in d
        assert "forecast" in d
        math_mod = d["modules"]["math"]
        assert math_mod["started"] == 1
        assert math_mod["mastered"] == 1
        assert math_mod["readiness"] > 0


def test_stats_anon_returns_empty():
    from api.index import app

    c = app.test_client()
    resp = c.get("/api/study/stats")
    assert resp.status_code == 200
    d = resp.get_json()
    assert d["modules"] == {}
    assert d["streak"]["current"] == 0


def test_due_cards_endpoint():
    from api.index import app

    engine = _make_engine()
    c = app.test_client()
    p1, p2, p3 = _auth_patches(engine)
    with p1, p2, p3:
        c.post("/api/study/progress", headers=AUTH_HEADERS, json={
            "module": "informatics",
            "cards": {
                "lesson1_o1": {"reps": 2, "streak": 1, "correct": 2, "wrong": 1,
                               "due": time.time() - 100},
            },
        })
        resp = c.get("/api/study/due-cards", headers=AUTH_HEADERS)
        assert resp.status_code == 200
        d = resp.get_json()
        assert d["total"] >= 1
        assert d["due"][0]["module"] == "informatics"
        assert d["due"][0]["key"] == "lesson1_o1"


def test_due_cards_anon():
    from api.index import app

    c = app.test_client()
    resp = c.get("/api/study/due-cards")
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 0


def test_quiz_generate_and_check():
    from api.index import app

    c = app.test_client()
    p1, p2, p3 = _auth_patches(engine=_make_engine())
    with p1, p2, p3:
        resp = c.post("/api/quiz/generate", json={"module": "math", "n": 5})
        assert resp.status_code == 200
        d = resp.get_json()
        assert d["ok"] is True
        assert len(d["items"]) == 5
        sid = d["sid"]

        first = d["items"][0]
        if first["type"] == "mcq":
            assert "options" in first
            assert "correct_idx" in first
            check_resp = c.post("/api/quiz/check", json={"sid": sid, "idx": 0, "value": first["correct_idx"]})
        else:
            check_resp = c.post("/api/quiz/check", json={"sid": sid, "idx": 0, "value": first["answer"] if "answer" in first else "wrong"})
        assert check_resp.status_code == 200
        cd = check_resp.get_json()
        assert cd["ok"] is True
        assert "correct" in cd


def test_quiz_generate_unknown_module():
    from api.index import app

    c = app.test_client()
    resp = c.post("/api/quiz/generate", json={"module": "fake"})
    assert resp.status_code == 400


def test_quiz_check_unknown_session():
    from api.index import app

    c = app.test_client()
    resp = c.post("/api/quiz/check", json={"sid": "abc123", "idx": 0, "value": "x"})
    assert resp.status_code == 404


def test_analytics_page_renders():
    from api.index import app

    c = app.test_client()
    # /analytics was merged into /stats (redirect)
    resp = c.get("/analytics")
    assert resp.status_code == 302
    assert "/stats" in resp.headers.get("Location", "")
    # OGE analytics now lives on /stats
    resp = c.get("/stats")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "s-streak" in html
