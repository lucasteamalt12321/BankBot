"""Тесты модуля физики (ОГЭ): данные, страница, запись прогресса в study_progress."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def app():
    import api.index as m

    importlib.reload(m)
    m.app.config.update({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    for fn in ("require_auth", "get_auth_token"):
        if hasattr(m, fn):
            setattr(m, fn, lambda *a, **k: None)
    return m.app


@pytest.fixture
def client(app):
    return app.test_client()


def _ids(seq):
    return [x.id for x in seq]


def test_formulas_count():
    from core.physics.formulas import FORMULAS

    assert len(FORMULAS) >= 50


def test_formulas_unique_ids_and_fields():
    from core.physics.formulas import FORMULAS

    ids = _ids(FORMULAS)
    assert len(ids) == len(set(ids))
    for f in FORMULAS:
        assert f.topic and f.title and f.formula


def test_formulas_topics_present():
    from core.physics.formulas import formulas_by_topic

    grouped = formulas_by_topic()
    for tp in ("Кинематика", "Динамика", "Давление", "Электричество", "Колебания и волны"):
        assert tp in grouped, tp
        assert len(grouped[tp]) >= 4


def test_tasks_count_and_fields():
    from core.physics.formulas import TASKS

    assert len(TASKS) >= 20
    ids = _ids(TASKS)
    assert len(ids) == len(set(ids))
    for t in TASKS:
        assert t.topic and t.question and t.answer is not None


def test_generators_present():
    from core.physics.formulas import GENERATORS

    assert len(GENERATORS) >= 5


def test_helper_lookup():
    from core.physics.formulas import task_by_id

    assert task_by_id("t01") is not None
    assert task_by_id("nope") is None


def test_physics_page_loads(client):
    resp = client.get("/physics")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Физика" in body
    assert "__PHYSICS_DATA__" not in body


def test_physics_page_embedded_formula(client):
    body = client.get("/physics").get_data(as_text=True)
    assert "Второй закон Ньютона" in body or "Закон Ома" in body


def _patched_client():
    from tests.unit.test_study_progress import AUTH_HEADERS, _auth_patches, _make_engine

    import api.index as m

    importlib.reload(m)
    engine = _make_engine()
    patches = _auth_patches(engine)
    for p in patches:
        p.start()
    return m.app.test_client(), patches, AUTH_HEADERS


def test_physics_progress_roundtrip():
    client, patches, headers = _patched_client()
    try:
        body = {
            "module": "physics",
            "cards": {
                "formula::f09": {"reps": 2, "interval": 3, "ease": 2.5,
                                 "correct": 2, "wrong": 0, "counter": 2, "streak": 2, "due": 0},
                "task::t04": {"reps": 1, "interval": 1, "ease": 2.5,
                              "correct": 1, "wrong": 0, "counter": 1, "streak": 1, "due": 0},
            },
        }
        r = client.post("/api/study/progress", headers=headers, json=body)
        assert r.status_code == 200 and r.get_json()["ok"] is True

        cards = client.get("/api/study/progress", headers=headers).get_json()["cards"]
        assert "physics" in cards
        assert "formula::f09" in cards["physics"] and "task::t04" in cards["physics"]
    finally:
        for p in patches:
            p.stop()
