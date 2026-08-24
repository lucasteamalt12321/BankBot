"""Тесты экзаменатора ОГЭ: сборная сессия, серверная проверка, запись прогресса."""

from __future__ import annotations

import pytest


def test_exam_page_loads(client):
    r = client.get("/exam")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Экзаменатор" in body
    assert "/api/exam/mixed" in body


def test_exam_mixed_session(client):
    import api.index as m

    r = client.get("/api/exam/mixed?n=6")
    assert r.status_code == 200
    d = r.get_json()
    assert d["sid"] and len(d["items"]) == 6
    assert d["sid"] in m._EXAM_SESSIONS
    mods = {i["module"] for i in d["items"]}
    assert mods <= {"math", "russian", "informatics"}
    for it in d["items"]:
        assert it["question"] and "answer" not in it and "_answer" not in it


def test_exam_check_grades_and_records():
    from tests.unit.test_study_progress import AUTH_HEADERS, _auth_patches, _make_engine

    import api.index as m

    engine = _make_engine()
    c = m.app.test_client()
    patches = _auth_patches(engine)
    try:
        for p in patches:
            p.start()
        d = c.get("/api/exam/mixed?n=5").get_json()
        sid = d["sid"]
        stored = m._EXAM_SESSIONS[sid]

        wrong = c.post("/api/exam/check", headers=AUTH_HEADERS,
                       json={"sid": sid, "idx": 0, "value": "__totally_wrong__"}).get_json()
        assert wrong["correct"] is False

        right = c.post("/api/exam/check", headers=AUTH_HEADERS,
                       json={"sid": sid, "idx": 1, "value": stored[1]["_answer"]}).get_json()
        assert right["correct"] is True and right["recorded"] is True

        with engine.connect() as conn:
            rows = conn.execute(
                __import__("sqlalchemy").text(
                    "SELECT module, card_key, streak FROM study_progress"
                )
            ).fetchall()
        by_key = {(r[0], r[1]): r[2] for r in rows}
        assert by_key[(stored[0]["module"], "task::" + stored[0]["key"])] == 0
        assert by_key[(stored[1]["module"], "task::" + stored[1]["key"])] == 1
    finally:
        for p in patches:
            p.stop()


def test_exam_check_unknown_session(client):
    r = client.post("/api/exam/check", json={"sid": "nope", "idx": 0, "value": "x"})
    assert r.status_code == 404


@pytest.fixture
def client(app_fixture):
    return app_fixture.test_client()


@pytest.fixture
def app_fixture():
    import api.index as m

    m.app.config["TESTING"] = True
    return m.app
