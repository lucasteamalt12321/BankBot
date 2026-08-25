"""Тесты модуля истории — термины (ОГЭ): данные, страница /terms, запись прогресса."""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def client():
    import api.index as m

    m.app.config["TESTING"] = True
    return m.app.test_client()


def test_terms_count():
    from core.history.terms import TERMS

    assert len(TERMS) >= 75


def test_terms_unique_ids_and_fields():
    from core.history.terms import TERMS

    ids = [t.id for t in TERMS]
    assert len(ids) == len(set(ids))
    for t in TERMS:
        assert t.category and t.term and t.definition


def test_terms_categories():
    from core.history.terms import categories, term_by_id

    cats = categories()
    assert len(cats) >= 5
    assert term_by_id("t01") is not None
    assert term_by_id("nope") is None


def test_terms_embedded_into_history_page(client):
    resp = client.get("/emperors")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "История" in body
    assert "terms-wrap" not in body
    assert 'id="tab-terms"' in body and 'id="panel-terms"' in body
    assert "t-cat" in body and 'id="t-inp"' in body and 'id="t-check"' in body
    assert ">Знаю<" not in body and "Показать определение" not in body
    assert "Опричнина" in body or "Полюдье" in body
    assert "__TERMS_DATA__" not in body


def test_terms_redirects_to_history(client):
    resp = client.get("/terms")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/emperors?tab=terms")


def test_history_terms_roundtrip():
    from tests.unit.test_study_progress import AUTH_HEADERS, _auth_patches, _make_engine

    import api.index as m

    engine = _make_engine()
    c = m.app.test_client()
    patches = _auth_patches(engine)
    try:
        for p in patches:
            p.start()
        r = c.post("/api/study/progress", headers=AUTH_HEADERS, json={
            "module": "history",
            "cards": {"term::t20": {"reps": 1, "streak": 1, "correct": 1, "wrong": 0, "due": 0}},
        })
        assert r.status_code == 200
        cards = c.get("/api/study/progress", headers=AUTH_HEADERS).get_json()["cards"]
        assert "term::t20" in cards["history"]
    finally:
        for p in patches:
            p.stop()
