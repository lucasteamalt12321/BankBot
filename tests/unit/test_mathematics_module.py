"""Тесты модуля математики (ОГЭ): данные, страница, запись прогресса в study_progress."""

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


# ---------- Данные ----------

def test_formulas_count():
    from core.mathematics.formulas import FORMULAS

    assert len(FORMULAS) >= 100


def test_formulas_unique_ids_and_fields():
    from core.mathematics.formulas import FORMULAS

    ids = _ids(FORMULAS)
    assert len(ids) == len(set(ids))
    for f in FORMULAS:
        assert f.topic and f.title and f.formula


def test_formulas_grouped_by_topic():
    from core.mathematics.formulas import formulas_by_topic

    grouped = formulas_by_topic()
    assert "Квадратный трёхчлен" in grouped
    assert len(grouped["Квадратный трёхчлен"]) >= 5


def test_tasks_count_and_fields():
    from core.mathematics.formulas import TASKS

    assert len(TASKS) >= 20
    ids = _ids(TASKS)
    assert len(ids) == len(set(ids))
    for t in TASKS:
        assert t.topic and t.question and t.answer is not None


def test_generators_present():
    from core.mathematics.formulas import GENERATORS

    assert len(GENERATORS) >= 5
    for g in GENERATORS:
        assert g.id and g.name


def test_helper_lookups():
    from core.mathematics.formulas import task_by_id, generator_by_id

    assert task_by_id("m01") is not None
    assert task_by_id("nope") is None
    assert generator_by_id("g01") is not None


# ---------- Страница ----------

def test_math_page_loads(client):
    resp = client.get("/math")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Математика" in body
    assert "Формулы" in body
    assert "__MATH_DATA__" not in body
    assert "MATH" in body


def test_math_page_embedded_formula(client):
    resp = client.get("/math")
    body = resp.get_data(as_text=True)
    assert "Дискриминант" in body or "Теорема Пифагора" in body


# ---------- Запись прогресса ----------

def _patched_client():
    from tests.unit.test_study_progress import _make_engine, _auth_patches, AUTH_HEADERS

    import api.index as m

    importlib.reload(m)
    engine = _make_engine()
    patches = _auth_patches(engine)
    for p in patches:
        p.start()
    client = m.app.test_client()
    return client, patches, AUTH_HEADERS


def test_math_progress_roundtrip():
    client, patches, headers = _patched_client()
    try:
        body = {
            "module": "math",
            "cards": {
                "formula::f11": {"reps": 3, "interval": 7, "ease": 2.5,
                                 "correct": 3, "wrong": 0, "counter": 3, "streak": 3, "due": 0},
                "task::m01": {"reps": 1, "interval": 1, "ease": 2.5,
                              "correct": 1, "wrong": 0, "counter": 1, "streak": 1, "due": 0},
            },
        }
        r = client.post("/api/study/progress", headers=headers, json=body)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        r2 = client.get("/api/study/progress", headers=headers)
        assert r2.status_code == 200
        cards = r2.get_json()["cards"]
        assert "math" in cards
        assert "formula::f11" in cards["math"]
        assert "task::m01" in cards["math"]
    finally:
        for p in patches:
            p.stop()


def test_math_progress_module_is_scoped():
    client, patches, headers = _patched_client()
    try:
        client.post("/api/study/progress", headers=headers, json={
            "module": "math",
            "cards": {"formula::f11": {"reps": 2, "streak": 2, "correct": 2, "wrong": 0, "due": 0}},
        })
        client.post("/api/study/progress", headers=headers, json={
            "module": "history",
            "cards": {"term::опричнина": {"reps": 1, "streak": 0, "correct": 1, "wrong": 2}},
        })
        data = client.get("/api/study/progress", headers=headers).get_json()
        assert set(data["cards"].keys()) == {"math", "history"}
        assert "formula::f11" in data["cards"]["math"]
        assert "term::опричнина" in data["cards"]["history"]
    finally:
        for p in patches:
            p.stop()
