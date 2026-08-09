"""E2E tests for CANON-02: works with full text, canonization requests, admin moderation."""

from __future__ import annotations

import io

from unittest.mock import patch

import pytest

from api.index import ADMIN_TELEGRAM_ID, app
from tests.unit.test_web_portal_e2e import _auth_headers, _make_engine


def _admin_token(client):
    resp = client.post("/api/auth/register", json={
        "login": "canonroot",
        "password": "secret123",
        "telegram_id": ADMIN_TELEGRAM_ID,
    })
    assert resp.status_code == 200
    return resp.get_json()["token"]


def _user_token(client, login="canonuser"):
    resp = client.post("/api/auth/register", json={"login": login, "password": "secret123"})
    assert resp.status_code == 200
    return resp.get_json()["token"]


@pytest.fixture()
def client():
    return app.test_client()


@patch("api.index.get_db_engine")
def test_canon_work_page_and_public_api(mock_engine):
    """Canon work pages + public APIs work with DB present and absent."""
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    works = c.get("/api/canon/works").get_json()
    assert works["total"] >= 1
    first_id = works["works"][0]["id"]

    page = c.get(f"/canon/work/{first_id}")
    assert page.status_code == 200
    assert "Канон" in page.get_data(as_text=True)

    detail = c.get(f"/api/canon/work/{first_id}")
    assert detail.status_code == 200
    assert "title" in detail.get_json()

    docs = c.get("/api/canon/documents").get_json()
    assert docs["source"] in ("db", "file")
    assert docs["text"]


def test_canon_work_page_missing_404():
    c = app.test_client()
    page = c.get("/canon/work/999999")
    assert page.status_code in (404, 500)


@patch("api.index.get_db_engine")
def test_request_submit_requires_auth(mock_engine):
    """Anonymous submit is rejected; DB failures fall back to 500, not a crash."""
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    anon = c.post("/api/canon/request", json={
        "title": "Трек", "author": "Автор", "content": "Полный текст",
    })
    assert anon.status_code == 401

    bad = c.post("/api/canon/request", json={"title": "", "author": "", "content": ""},
                 headers=_auth_headers(_user_token(c)))
    assert bad.status_code == 400


@patch("api.index.get_db_engine")
def test_request_submit_validation(mock_engine):
    mock_engine.return_value = _make_engine()
    c = app.test_client()
    token = _user_token(c)

    too_long = c.post("/api/canon/request", json={
        "title": "x" * 201, "author": "a", "content": "text",
    }, headers=_auth_headers(token))
    assert too_long.status_code == 400

    bad_level = c.post("/api/canon/request", json={
        "title": "Т", "author": "а", "content": "текст", "canon_level": "invalid",
    }, headers=_auth_headers(token))
    assert bad_level.status_code == 400

    ok = c.post("/api/canon/request", json={
        "title": "Новый трек", "kind": "track", "author": "Канон-автор",
        "content": "Полный текст произведения", "canon_level": "high",
    }, headers=_auth_headers(token))
    assert ok.status_code == 200


@patch("api.index.get_db_engine")
def test_admin_moderation_flow(mock_engine):
    """Submit request -> approve -> appears in works -> edit -> document overlay."""
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    user_token = _user_token(c)
    admin_token = _admin_token(c)

    c.post("/api/canon/request", json={
        "title": "Трек Ада", "kind": "track", "author": "Ада",
        "content": "Текст трека", "canon_level": "high",
    }, headers=_auth_headers(user_token))

    no_access = c.get("/api/admin/canon/requests")
    assert no_access.status_code == 403

    listing = c.get("/api/admin/canon/requests", headers=_auth_headers(admin_token))
    assert listing.status_code == 200
    pending = [r for r in listing.get_json()["items"] if r["status"] == "pending"]
    assert any(r["title"] == "Трек Ада" for r in pending)
    req_id = next(r["id"] for r in pending if r["title"] == "Трек Ада")

    approve = c.post(f"/api/admin/canon/requests/{req_id}/approve", json={},
                     headers=_auth_headers(admin_token))
    assert approve.status_code == 200

    works = c.get("/api/canon/works?level=high").get_json()
    assert any(w["title"] == "Трек Ада" for w in works["works"])

    new_work = next(w for w in works["works"] if w["title"] == "Трек Ада")
    detail = c.get(f"/api/canon/work/{new_work['id']}").get_json()
    assert detail["content"] == "Текст трека"

    edited = c.put(f"/api/admin/canon/works/{new_work['id']}", json={
        "title": "Трек Ады", "author": "Ада Б.", "canon_level": "medium",
        "content": "Обновлённый текст",
    }, headers=_auth_headers(admin_token))
    assert edited.status_code == 200
    after = c.get(f"/api/canon/work/{new_work['id']}").get_json()
    assert after["title"] == "Трек Ады"
    assert after["content"] == "Обновлённый текст"

    not_admin = c.put(f"/api/admin/canon/works/{new_work['id']}",
                      json={"title": "x", "content": "y"}, headers=_auth_headers(user_token))
    assert not_admin.status_code == 403


@patch("api.index.get_db_engine")
def test_admin_reject_and_doc_overlay(mock_engine):
    """Reject request; document overlay PUT/DELETE roundtrip."""
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    admin_token = _admin_token(c)
    c.post("/api/canon/request", json={
        "title": "Отклонённый", "author": "Кто-то", "content": "Текст",
    }, headers=_auth_headers(_user_token(c)))

    listing = c.get("/api/admin/canon/requests", headers=_auth_headers(admin_token)).get_json()
    req_id = next(r["id"] for r in listing["items"] if r["title"] == "Отклонённый")

    reject = c.post(f"/api/admin/canon/requests/{req_id}/reject",
                    json={"review_note": "Не канон"}, headers=_auth_headers(admin_token))
    assert reject.status_code == 200

    after = c.get("/api/canon/works").get_json()
    assert all(w["title"] != "Отклонённый" for w in after["works"])

    orig = c.get("/api/canon/documents").get_json()
    doc = c.get("/api/admin/canon/doc", headers=_auth_headers(admin_token)).get_json()
    assert doc["content"] == orig["text"]

    new_text = "# Канон\nПравка админа"
    put = c.put("/api/admin/canon/doc", json={"content": new_text},
                headers=_auth_headers(admin_token))
    assert put.status_code == 200

    changed = c.get("/api/canon/documents").get_json()
    assert changed["source"] == "db"
    assert changed["text"] == new_text

    reset = c.delete("/api/admin/canon/doc", headers=_auth_headers(admin_token))
    assert reset.status_code == 200
    back = c.get("/api/canon/documents").get_json()
    assert back["source"] in ("db", "file")
    assert back["text"]


@patch("api.index.get_db_engine")
def test_audio_upload_stream_delete(mock_engine):
    """Admin uploads audio for a track -> public stream -> has_audio in API -> delete."""
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    user_token = _user_token(c)
    admin_token = _admin_token(c)

    c.post("/api/canon/request", json={
        "title": "Трек с аудио", "kind": "track", "author": "Автор",
        "content": "Текст", "canon_level": "high",
    }, headers=_auth_headers(user_token))

    listing = c.get("/api/admin/canon/requests", headers=_auth_headers(admin_token)).get_json()
    req_id = next(r["id"] for r in listing["items"] if r["title"] == "Трек с аудио")
    c.post(f"/api/admin/canon/requests/{req_id}/approve", json={}, headers=_auth_headers(admin_token))

    works = c.get("/api/canon/works").get_json()
    work = next(w for w in works["works"] if w["title"] == "Трек с аудио")
    assert work["has_audio"] is False

    anon_upload = c.post(
        f"/api/admin/canon/works/{work['id']}/audio",
        data={"audio": (io.BytesIO(b"fake-mp3-bytes"), "track.mp3")},
        content_type="multipart/form-data",
    )
    assert anon_upload.status_code == 403

    bad_ext = c.post(
        f"/api/admin/canon/works/{work['id']}/audio",
        data={"audio": (io.BytesIO(b"data"), "track.exe")},
        content_type="multipart/form-data",
        headers=_auth_headers(admin_token),
    )
    assert bad_ext.status_code == 400

    upload = c.post(
        f"/api/admin/canon/works/{work['id']}/audio",
        data={"audio": (io.BytesIO(b"fake-mp3-bytes"), "track.mp3")},
        content_type="multipart/form-data",
        headers=_auth_headers(admin_token),
    )
    assert upload.status_code == 200
    assert upload.get_json()["ok"] is True

    works_after = c.get("/api/canon/works").get_json()
    work_after = next(w for w in works_after["works"] if w["title"] == "Трек с аудио")
    assert work_after["has_audio"] is True
    assert work_after["audio_name"] == "track.mp3"

    detail = c.get(f"/api/canon/work/{work['id']}").get_json()
    assert detail["has_audio"] is True
    assert detail["audio_mime"] == "audio/mpeg"

    page = c.get(f"/canon/work/{work['id']}")
    body = page.get_data(as_text=True)
    assert "audio-card" in body
    assert "/api/canon/work/{}/audio".format(work["id"]) in body

    stream = c.get(f"/api/canon/work/{work['id']}/audio")
    assert stream.status_code == 200
    assert stream.mimetype == "audio/mpeg"
    assert stream.data == b"fake-mp3-bytes"

    missing = c.get("/api/canon/work/999999/audio")
    assert missing.status_code == 404

    remove = c.delete(f"/api/admin/canon/works/{work['id']}/audio", headers=_auth_headers(admin_token))
    assert remove.status_code == 200

    stream_after = c.get(f"/api/canon/work/{work['id']}/audio")
    assert stream_after.status_code == 404

    works_final = c.get("/api/canon/works").get_json()
    work_final = next(w for w in works_final["works"] if w["title"] == "Трек с аудио")
    assert work_final["has_audio"] is False


@patch("api.index.get_db_engine")
def test_admin_pages_render(mock_engine):
    """Admin + request pages render (access control happens via JS/API)."""
    mock_engine.return_value = _make_engine()
    c = app.test_client()

    page = c.get("/admin/canon")
    assert page.status_code == 200
    assert "Заявки" in page.get_data(as_text=True)
    assert "web_token" in page.get_data(as_text=True)

    req_page = c.get("/canon/request")
    assert req_page.status_code == 200
    body = req_page.get_data(as_text=True)
    assert "заявк" in body
    assert "web_token" in body
