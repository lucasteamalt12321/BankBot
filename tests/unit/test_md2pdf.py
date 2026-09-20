"""Tests for the Markdown → PDF module page (GET /md2pdf)."""

from api.index import app


def _get_page():
    client = app.test_client()
    return client.get("/md2pdf")


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