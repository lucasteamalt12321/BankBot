"""Tests for the Markdown → PDF module page (GET /md2pdf).

Freemium FRE-06: /api/md2pdf/format требует авторизации (401 {auth_required}).
API-тесты используют in-memory движок (паттерн test_achievements), потому что
реальный get_db_engine в этой среде уводит log_error в Telegram-запрос.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from api.index import app


def _get_page():
    client = app.test_client()
    return client.get("/md2pdf")


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    raw = engine.raw_connection()
    raw.create_function("NOW", 0, lambda: datetime.now(timezone.utc).isoformat())
    raw.close()
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE web_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login VARCHAR(64) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(100),
                gd_nickname VARCHAR(64),
                telegram_id BIGINT,
                lichess_nickname VARCHAR(64),
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ,
                email VARCHAR(255) UNIQUE,
                created_via VARCHAR(32)
            )
        """))
        conn.execute(text("""
            CREATE TABLE web_sessions (
                token VARCHAR(64) PRIMARY KEY,
                user_id INTEGER,
                created_at TIMESTAMPTZ
            )
        """))
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


_REG = {"engine": None, "token": None}


def _fixture():
    """One in-memory engine + registered user (token) per pytest process."""
    if _REG["token"]:
        return _REG["engine"], _REG["token"]
    engine = _make_engine()
    with patch("api.index.get_db_engine", return_value=engine):
        client = app.test_client()
        login = "md" + uuid.uuid4().hex[:10]
        resp = client.post(
            "/api/auth/register",
            json={"login": login, "password": "secret1", "display_name": "MD Test"},
        )
        data = resp.get_json() or {}
        assert resp.status_code == 200, data
        _REG["engine"] = engine
        _REG["token"] = data["token"]
    return engine, data["token"]


def test_md2pdf_page_ok():
    resp = _get_page()
    assert resp.status_code == 200
    assert "text/html" in resp.content_type


def test_md2pdf_has_editor_and_preview():
    body = _get_page().get_data(as_text=True)
    assert 'id="mdInput"' in body
    assert 'id="pdfPage"' in body
    assert "pdf-page" in body


def test_md2pdf_has_download_and_helpers():
    body = _get_page().get_data(as_text=True)
    assert "Скачать PDF" in body
    assert "printFrame" in body
    assert "downloadPdf" in body
    assert "loadSample" in body


def test_md2pdf_uses_marked_and_highlight():
    body = _get_page().get_data(as_text=True)
    assert "marked" in body
    assert "highlight.js" in body
    assert "marked.parse" in body


def test_md2pdf_has_ai_format_button():
    body = _get_page().get_data(as_text=True)
    assert "Улучшить форматирование" in body
    assert "improveMd" in body
    assert "/api/md2pdf/format" in body
    assert "ИИ временно недоступен" in body


def test_md2pdf_has_font_size_control():
    body = _get_page().get_data(as_text=True)
    assert "Размер шрифта" in body
    assert 'id="fontSize"' in body
    assert "applyFontSize" in body
    assert "stepFontSize" in body
    assert "printCss" in body


def test_md2pdf_format_requires_auth():
    engine, _ = _fixture()
    client = app.test_client()
    with patch("api.index.get_db_engine", return_value=engine):
        resp = client.post("/api/md2pdf/format", json={"text": "# Hi"})
    assert resp.status_code == 401
    body = resp.get_json() or {}
    assert body.get("auth_required") is True


def test_md2pdf_format_endpoint_rejects_empty():
    engine, token = _fixture()
    client = app.test_client()
    with patch("api.index.get_db_engine", return_value=engine):
        resp = client.post(
            "/api/md2pdf/format",
            json={"text": "   "},
            headers={"X-Auth-Token": token},
        )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_md2pdf_format_endpoint_rejects_too_long():
    engine, token = _fixture()
    client = app.test_client()
    with patch("api.index.get_db_engine", return_value=engine):
        resp = client.post(
            "/api/md2pdf/format",
            json={"text": "x" * 20001},
            headers={"X-Auth-Token": token},
        )
    assert resp.status_code == 400
    assert "error" in resp.get_json()