"""Tests for OGE curator: persistent daily plan + chat history (OGE-08/09)."""

import json

from unittest.mock import patch

from tests.unit.test_study_progress import AUTH_HEADERS, _auth_patches, _make_engine


def _setup():
    import api.index as m

    engine = _make_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS oge_daily_plans (
                user_id INTEGER NOT NULL,
                plan_date TEXT NOT NULL,
                target_minutes INTEGER NOT NULL DEFAULT 10,
                items_json TEXT NOT NULL DEFAULT '[]',
                source VARCHAR(16) NOT NULL DEFAULT 'rule',
                done_count INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, plan_date)
            )
        """)
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS oge_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role VARCHAR(12) NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL DEFAULT 0
            )
        """)
    c = m.app.test_client()
    patches = list(_auth_patches(engine))
    for p in patches:
        p.start()
    return m, c, patches


def _stop(patches):
    for p in patches:
        p.stop()


def _ai_plan_json(n=3):
    mods = ["math", "russian", "informatics", "history", "physics"]
    return json.dumps([
        {"module": mods[i % 5], "text": f"Действие {i + 1}", "minutes": 5}
        for i in range(n)
    ])


def test_anon_401_on_all_curator_endpoints():
    import api.index as m

    engine = _make_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS oge_daily_plans (user_id INTEGER NOT NULL, plan_date TEXT NOT NULL, target_minutes INTEGER NOT NULL DEFAULT 10, items_json TEXT NOT NULL DEFAULT '[]', source VARCHAR(16) NOT NULL DEFAULT 'rule', done_count INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL DEFAULT 0, PRIMARY KEY (user_id, plan_date))")
        conn.exec_driver_sql("CREATE TABLE IF NOT EXISTS oge_chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, role VARCHAR(12) NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL DEFAULT 0)")
    c = m.app.test_client()
    p = patch("api.index.get_db_engine", return_value=engine)
    p.start()
    try:
        assert c.get("/api/study/plan").status_code == 401
        assert c.post("/api/study/plan", json={}).status_code == 401
        assert c.post("/api/study/plan/done", json={"delta": 1}).status_code == 401
        assert c.get("/api/study/chat").status_code == 401
        assert c.post("/api/study/chat", json={"message": "привет"}).status_code == 401
        assert c.get("/api/study/today").status_code == 401
    finally:
        p.stop()


def test_plan_generated_once_per_day_and_cached():
    m, c, patches = _setup()
    try:
        with patch.object(m, "call_ai_api", return_value=_ai_plan_json(4)) as ai:
            r1 = c.get("/api/study/plan", headers=AUTH_HEADERS).get_json()
            calls_after_first = ai.call_count
            r2 = c.get("/api/study/plan", headers=AUTH_HEADERS).get_json()
            assert ai.call_count == calls_after_first
        assert r1["ok"] and r2["ok"]
        assert r1["items"] == r2["items"]
        assert len(r1["items"]) == 4
        assert r1["target_minutes"] == 10
        assert r1["source"] == "ai"
    finally:
        _stop(patches)


def test_plan_regenerates_when_minutes_change():
    m, c, patches = _setup()
    try:
        with patch.object(m, "call_ai_api", return_value=_ai_plan_json(3)) as ai:
            first = c.get("/api/study/plan", headers=AUTH_HEADERS).get_json()
            n1 = ai.call_count
            second = c.get("/api/study/plan?minutes=20", headers=AUTH_HEADERS).get_json()
            assert ai.call_count > n1
            third = c.get("/api/study/plan?minutes=20", headers=AUTH_HEADERS).get_json()
            n3 = ai.call_count
            fourth = c.get("/api/study/plan?minutes=20", headers=AUTH_HEADERS).get_json()
            assert ai.call_count == n3
        assert first["target_minutes"] == 10
        assert second["target_minutes"] == 20
        assert fourth["items"] == third["items"]
    finally:
        _stop(patches)


def test_plan_post_explicit_regen_and_fallback_to_rules():
    m, c, patches = _setup()
    try:
        with patch.object(m, "call_ai_api", return_value="❌ Ошибка AI: 404"):
            r = c.post("/api/study/plan", json={"minutes": 5}, headers=AUTH_HEADERS).get_json()
        assert r["ok"] and r["source"] == "rule"
        assert 2 <= len(r["items"]) <= 6
        assert all(set(it) >= {"module", "label", "text", "url"} for it in r["items"])
    finally:
        _stop(patches)


def test_done_delta_updates_counter():
    m, c, patches = _setup()
    try:
        with patch.object(m, "call_ai_api", return_value=_ai_plan_json(3)):
            c.get("/api/study/plan", headers=AUTH_HEADERS)
        d1 = c.post("/api/study/plan/done", json={"delta": 1}, headers=AUTH_HEADERS).get_json()
        d2 = c.post("/api/study/plan/done", json={"delta": 1}, headers=AUTH_HEADERS).get_json()
        d3 = c.post("/api/study/plan/done", json={"delta": -1}, headers=AUTH_HEADERS).get_json()
        d4 = c.post("/api/study/plan/done", json={"delta": -1}, headers=AUTH_HEADERS).get_json()
        d5 = c.post("/api/study/plan/done", json={"delta": -1}, headers=AUTH_HEADERS).get_json()
        assert (d1["done"], d2["done"], d3["done"], d4["done"], d5["done"]) == (1, 2, 1, 0, 0)
        today = c.get("/api/study/plan", headers=AUTH_HEADERS).get_json()
        assert today["done"] == 0
    finally:
        _stop(patches)


def test_yesterday_low_completion_eases_rule_plan():
    m, c, patches = _setup()
    try:
        import time as _t
        yday = m._prev_day(_t.strftime("%Y-%m-%d"))
        big = [{"module": "math", "label": "📐 Математика", "text": f"t{i}", "url": "/math", "minutes": 5} for i in range(6)]
        with m.get_db_engine().begin() as conn:
            conn.execute(m.text(
                "INSERT INTO oge_daily_plans (user_id, plan_date, target_minutes, items_json, source, done_count, created_at)"
                " VALUES (1, :d, 30, :j, 'rule', 1, 0)"
            ), {"d": yday, "j": json.dumps(big)})
        with patch.object(m, "call_ai_api", return_value="❌"):
            eased = m._generate_plan(1, _t.strftime("%Y-%m-%d"), 15)[0]
        with patch.object(m, "call_ai_api", return_value="❌"):
            normal = m._generate_plan(2, _t.strftime("%Y-%m-%d"), 15)[0]
        assert len(eased) < len(normal)
        assert m._yesterday_completion(1, _t.strftime("%Y-%m-%d")) == 1 / 6
    finally:
        _stop(patches)


def test_chat_persists_history_and_prompt_context():
    m, c, patches = _setup()
    try:
        captured = {}

        def fake_ai(prompt, max_tokens=150, temperature=0.8):
            captured["prompt"] = prompt
            return "Советую начать с математики."

        with patch.object(m, "call_ai_api", side_effect=fake_ai):
            with patch.object(m, "_oge_subjects_payload", return_value=[{
                "module": "math", "label": "Математика", "emoji": "📐", "url": "/math",
                "due": 2, "weak": 1, "started": 5, "total": 130, "urgency": 2.0, "score": 31.0,
                "next_action": {"text": "Повторить 2 карточек", "url": "/math?algo=flash"},
            }]):
                r1 = c.post("/api/study/chat", json={"message": "Привет! Что делать?"},
                            headers=AUTH_HEADERS).get_json()
                # ensure a plan exists so the prompt includes it
                with patch.object(m, "call_ai_api", return_value=_ai_plan_json(3)):
                    plan = c.get("/api/study/plan", headers=AUTH_HEADERS).get_json()
                r2 = c.post("/api/study/chat", json={"message": "А по русскому?"},
                            headers=AUTH_HEADERS).get_json()

        assert r1["ok"] and r2["ok"]
        p = captured["prompt"]
        assert "Привет! Что делать?" in p or "А по русскому?" in p
        hist = c.get("/api/study/chat", headers=AUTH_HEADERS).get_json()["messages"]
        roles = [x["role"] for x in hist]
        assert roles.count("user") == 2 and roles.count("assistant") == 2
        joined = "\n".join(x["content"] for x in hist)
        assert "Советую начать" in joined
        assert f'{plan["done"]} из' in p or "План на сегодня" in p
        assert "Повторить 2 карточек" in p
        assert "История переписки" in p
    finally:
        _stop(patches)


def test_chat_ai_failure_falls_back_to_rule_reply_and_persists():
    m, c, patches = _setup()
    try:
        with patch.object(m, "call_ai_api", return_value="❌ Ошибка AI: 404"):
            r = c.post("/api/study/chat", json={"message": "тест"}, headers=AUTH_HEADERS)
        assert r.status_code == 200
        d = r.get_json()
        assert d["ok"] and d.get("reply") and "❌" not in d["reply"]
        hist = c.get("/api/study/chat", headers=AUTH_HEADERS).get_json()["messages"]
        roles = [x["role"] for x in hist]
        assert roles.count("user") == 1 and roles.count("assistant") == 1
    finally:
        _stop(patches)


def test_today_touched_endpoint_counts_rows():
    m, c, patches = _setup()
    try:
        import time as _t
        uid = c.get("/api/study/recommendations", headers=AUTH_HEADERS).get_json()["uid"]
        assert uid
        with m.get_db_engine().begin() as conn:
            conn.execute(m.text(
                "INSERT INTO study_progress (user_id, module, card_key, reps, interval_days, ease,"
                " due, streak, correct_count, wrong_count, counter, updated_at)"
                " VALUES (:u,'math','formula::f01',1,1,2.5,:due,1,1,0,1,:ts)"
            ), {"u": uid, "due": _t.time() + 100, "ts": _t.time()})
        d = c.get("/api/study/today", headers=AUTH_HEADERS).get_json()
        assert d["ok"] and d["touched"] >= 1
    finally:
        _stop(patches)


def test_hint_unknown_module_400_and_anon_generic():
    import api.index as m

    engine = _make_engine()
    c = m.app.test_client()
    p = patch("api.index.get_db_engine", return_value=engine)
    p.start()
    try:
        assert c.get("/api/study/hint?module=nope").status_code == 400
        d = c.get("/api/study/hint?module=math").get_json()
        assert d["ok"] and "карточки" in d["text"] and d["url"] == "/math"
    finally:
        p.stop()


def test_hint_due_weak_and_fresh_scenarios():
    m, c, patches = _setup()
    try:
        uid = c.get("/api/study/recommendations", headers=AUTH_HEADERS).get_json()["uid"]
        import time as _t
        now = _t.time()
        with m.get_db_engine().begin() as conn:
            conn.execute(m.text(
                "INSERT INTO study_progress (user_id, module, card_key, reps, interval_days, ease,"
                " due, streak, correct_count, wrong_count, counter, updated_at)"
                " VALUES (:u,'math','formula::f01',0,0,2.5,:past,0,0,3,-2,:ts)"
            ), {"u": uid, "past": now - 10, "ts": now})
            conn.execute(m.text(
                "INSERT INTO study_progress (user_id, module, card_key, reps, interval_days, ease,"
                " due, streak, correct_count, wrong_count, counter, updated_at)"
                " VALUES (:u,'russian','rule::r01',1,1,2.5,:future,1,1,0,1,:ts),"
                " (:u,'russian','rule::r02',0,0,2.5,:future,0,0,2,-1,:ts)"
            ), {"u": uid, "future": now + 99999, "ts": now})
        d1 = c.get("/api/study/hint?module=math", headers=AUTH_HEADERS).get_json()
        assert d1["ok"] and "Повторите" in d1["text"] and "формул" in d1["text"]
        assert d1["mode"] == "flash"
        d2 = c.get("/api/study/hint?module=russian", headers=AUTH_HEADERS).get_json()
        assert d2["ok"] and ("слабых" in d2["text"])
        with m.get_db_engine().begin() as conn:
            conn.execute(m.text("DELETE FROM study_progress WHERE user_id=:u AND module='math'"),
                         {"u": uid})
        d3 = c.get("/api/study/hint?module=math", headers=AUTH_HEADERS).get_json()
        assert d3["ok"] and "Начните" in d3["text"]
    finally:
        _stop(patches)


def test_subject_pages_get_hint_snippet_injected():
    m, c, patches = _setup()
    try:
        for page in ("/math", "/physics", "/russian", "/emperors"):
            html = c.get(page).get_data(as_text=True)
            assert "api/study/hint?module=" in html, page
            assert 'id="ai-hint-bar"' not in html  # создаётся только из JS
    finally:
        _stop(patches)


def test_tool_directive_parsing():
    import api.index as m

    assert m._tool_directive('{"tool":"progress","module":"math"}') == {"tool": "progress", "module": "math"}
    assert m._tool_directive('Вот ответ.\n{"tool":"stats"}')["tool"] == "stats"
    assert m._tool_directive("Обычный текст без JSON") is None
    assert m._tool_directive('{"tool":"unknown_tool"}') is None
    assert m._tool_directive("") is None
    assert m._tool_directive(None) is None


def test_curator_tool_data_progress_plan_stats():
    m, c, patches = _setup()
    try:
        uid = c.get("/api/study/recommendations", headers=AUTH_HEADERS).get_json()["uid"]
        import time as _t
        with m.get_db_engine().begin() as conn:
            conn.execute(m.text(
                "INSERT INTO study_progress (user_id, module, card_key, reps, interval_days, ease,"
                " due, streak, correct_count, wrong_count, counter, updated_at)"
                " VALUES (:u,'math','formula::f01',2,1,2.5,:past,3,4,1,-1,:ts),"
                " (:u,'math','task::lesson1_o1',0,0,2.5,:future,0,0,3,-2,:ts),"
                " (:u,'math','task::lesson2_o3',1,0,2.5,:future,1,1,1,0,:ts)"
            ), {"u": uid, "past": _t.time() - 10, "future": _t.time() + 9999, "ts": _t.time()})
        data = m._curator_tool_data({"tool": "progress", "module": "math"}, uid, "2026-01-01")
        assert "Математика" in data
        assert "выучено" in data and "к повторению сегодня" in data
        weak_part = data.split("Слабые карточки: ")[1].split(". Ключи")[0]
        assert "lesson1_o1" in weak_part and "formula::f01" not in weak_part  # выученная не в слабых
        # фильтр по теме
        topic = m._curator_tool_data({"tool": "progress", "module": "math", "topic": "lesson1"}, uid, "x")
        assert "lesson1_o1" in topic and "lesson2_o3" not in topic and "formula::f01" not in topic
        empty = m._curator_tool_data({"tool": "progress", "module": "math", "topic": "nope"}, uid, "x")
        assert "записей в журнале нет" in empty
        # отдельная карточка
        card = m._curator_tool_data({"tool": "card", "key": "formula::f01", "module": "math"}, uid, "x")
        assert "выучена" in card and "серия верных подряд 3" in card and "неверно 1" in card
        weak_card = m._curator_tool_data({"tool": "card", "key": "task::lesson1_o1"}, uid, "x")
        assert "верно 0 / неверно 3" in weak_card and "выучена" not in weak_card
        missing = m._curator_tool_data({"tool": "card", "key": "formula::zzz"}, uid, "x")
        assert "не найдена" in missing
        assert m._curator_tool_action({"tool": "progress", "module": "math"})
        assert "Математика" in m._curator_tool_action({"tool": "progress", "module": "math"})
        assert "lesson1" in m._curator_tool_action({"tool": "progress", "module": "math", "topic": "lesson1"})
        assert "formula::f01" in m._curator_tool_action({"tool": "card", "key": "formula::f01"})
        assert m._curator_tool_action({"tool": "stats"}) == "смотрит твою статистику 📊"
        plan_data = m._curator_tool_data({"tool": "plan"}, uid, _t.strftime("%Y-%m-%d"))
        assert "План" in plan_data
        stats = m._curator_tool_data({"tool": "stats"}, uid, "x")
        assert "Физика" in stats and "История" in stats
    finally:
        _stop(patches)


def test_chat_tool_roundtrip_and_actions():
    m, c, patches = _setup()
    try:
        calls = []

        def fake_ai(prompt, max_tokens=150, temperature=0.8):
            calls.append(prompt)
            if len(calls) == 1:
                return '{"tool":"progress","module":"math"}'
            return "Финальный ответ с **жирным**."

        with patch.object(m, "call_ai_api", side_effect=fake_ai):
            r = c.post("/api/study/chat", json={"message": "Как мой прогресс по математике?"},
                       headers=AUTH_HEADERS).get_json()
        assert r["ok"] and r["reply"] == "Финальный ответ с **жирным**."
        assert r["actions"] and "журнал" in r["actions"][0]
        assert len(calls) == 2
        assert "Система передала данные" in calls[1]
        hist = c.get("/api/study/chat", headers=AUTH_HEADERS).get_json()["messages"]
        roles = [x["role"] for x in hist]
        assert roles.count("user") == 1 and roles.count("assistant") == 1
        assert hist[-1]["content"] == "Финальный ответ с **жирным**."
        assert '{"tool"' not in "\n".join(x["content"] for x in hist)
    finally:
        _stop(patches)


def test_chat_second_call_failure_still_answers():
    m, c, patches = _setup()
    try:
        calls = []

        def fake_ai(prompt, max_tokens=150, temperature=0.8):
            calls.append(prompt)
            return '{"tool":"stats"}' if len(calls) == 1 else "❌ Ошибка AI: 503"

        with patch.object(m, "call_ai_api", side_effect=fake_ai):
            r = c.post("/api/study/chat", json={"message": "статистика?"}, headers=AUTH_HEADERS).get_json()
        assert r["ok"] and "❌" not in r["reply"]
        assert r["actions"], "lookup должен быть зафиксирован даже при сбое второго вызова"
    finally:
        _stop(patches)
