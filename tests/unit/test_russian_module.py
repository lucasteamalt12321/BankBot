"""Тесты модуля русского языка (ОГЭ): данные, страница, запись прогресса в study_progress."""

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

def test_rules_count():
    from core.russian.rules import RULES

    assert len(RULES) >= 35


def test_rules_unique_ids_and_fields():
    from core.russian.rules import RULES

    ids = _ids(RULES)
    assert len(ids) == len(set(ids))
    for r in RULES:
        assert r.category and r.title and r.rule and r.example


def test_rules_categories_present():
    from core.russian.rules import rules_by_category

    cats = rules_by_category()
    assert "Орфография" in cats
    assert "Пунктуация" in cats
    assert "Работа с текстом" in cats


def test_tasks_count_and_fields():
    from core.russian.rules import TASKS

    assert len(TASKS) >= 20
    ids = _ids(TASKS)
    assert len(ids) == len(set(ids))
    for t in TASKS:
        assert t.topic and t.question and t.answer is not None


def test_essay_criteria_present():
    from core.russian.rules import ESSAY_CRITERIA

    assert len(ESSAY_CRITERIA) >= 10
    codes = [c.code for c in ESSAY_CRITERIA]
    assert "К1" in codes and "К12" in codes


# ---------- Страница ----------

def test_russian_page_loads(client):
    resp = client.get("/russian")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Русский язык" in body
    assert "Чек-лист сочинения" in body
    assert "__RUSSIAN_DATA__" not in body


def test_russian_page_embedded_rules(client):
    resp = client.get("/russian")
    body = resp.get_data(as_text=True)
    assert "безударн" in body.lower() or "НЕ слитно" in body


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


def test_russian_progress_roundtrip():
    client, patches, headers = _patched_client()
    try:
        body = {
            "module": "russian",
            "cards": {
                "rule::r01": {"reps": 3, "interval": 7, "ease": 2.5,
                              "correct": 3, "wrong": 0, "counter": 3, "streak": 3, "due": 0},
                "task::t01": {"reps": 1, "interval": 1, "ease": 2.5,
                              "correct": 1, "wrong": 0, "counter": 1, "streak": 1, "due": 0},
                "essay::e1": {"reps": 1, "interval": 1, "ease": 2.5,
                              "correct": 1, "wrong": 0, "counter": 1, "streak": 1, "due": 0},
            },
        }
        r = client.post("/api/study/progress", headers=headers, json=body)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

        data = client.get("/api/study/progress", headers=headers).get_json()
        assert "russian" in data["cards"]
        assert "rule::r01" in data["cards"]["russian"]
        assert "task::t01" in data["cards"]["russian"]
        assert "essay::e1" in data["cards"]["russian"]
    finally:
        for p in patches:
            p.stop()
