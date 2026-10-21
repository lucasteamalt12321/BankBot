"""Tests for the Render relay (relay/app.py)."""

from __future__ import annotations

import pytest
import requests as requests_lib
from requests.structures import CaseInsensitiveDict

import relay.app as relay_app


class _FakeUpstream:
    """Минимальный requests.Response для подстановки вместо апстрима."""

    def __init__(self, status=200, headers=None, chunks=None):
        self.status_code = status
        self.headers = CaseInsensitiveDict(headers or {})
        self._chunks = list(chunks or [])
        self.closed = False

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


def _stub_send(monkeypatch, response=None, error=None):
    calls = []

    def _send(method, url, *, headers, params, data):
        calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
                "data": data,
            }
        )
        if error is not None:
            raise error
        assert response is not None
        return response

    monkeypatch.setattr(relay_app, "_send", _send)
    return calls


@pytest.fixture()
def client():
    relay_app.app.config["TESTING"] = True
    return relay_app.app.test_client()


def test_health_is_local(client, monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("health must not call upstream")

    monkeypatch.setattr(relay_app, "_send", _fail)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_main_route_forwards_to_main_upstream(client, monkeypatch):
    fake = _FakeUpstream(chunks=[b"page"])
    calls = _stub_send(monkeypatch, fake)
    resp = client.get("/family_budget?x=1&x=2")
    assert resp.status_code == 200
    call = calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://lthub.vercel.app/family_budget"
    assert call["params"] == [("x", "1"), ("x", "2")]
    assert call["data"] is None
    assert call["headers"]["Accept-Encoding"] == "identity"
    assert "127.0.0.1" in call["headers"]["X-Forwarded-For"]
    lower = {key.lower() for key in call["headers"]}
    assert "host" not in lower
    assert "connection" not in lower
    assert "content-length" not in lower
    assert resp.data == b"page"
    assert fake.closed


def test_root_forwards_to_main_upstream(client, monkeypatch):
    calls = _stub_send(monkeypatch, _FakeUpstream(chunks=[b"root"]))
    resp = client.get("/")
    assert calls[0]["url"] == "https://lthub.vercel.app/"
    assert resp.status_code == 200


def test_audio_route_uses_audio_upstream(client, monkeypatch):
    calls = _stub_send(monkeypatch, _FakeUpstream(chunks=[b"{}"]))
    resp = client.post("/api/music/analyze", data=b"blob", content_type="audio/wav")
    assert resp.status_code == 200
    call = calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://audioservice.vercel.app/api/music/analyze"
    assert call["data"] == b"blob"


def test_html_music_base_rewritten(client, monkeypatch):
    html = b'<script>var MUSIC_API_BASE="https://audioservice.vercel.app";</script>'
    _stub_send(
        monkeypatch,
        _FakeUpstream(
            status=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            chunks=[html],
        ),
    )
    resp = client.get("/music")
    assert resp.status_code == 200
    assert b'MUSIC_API_BASE=""' in resp.data
    assert b"audioservice.vercel.app" not in resp.data
    assert resp.headers["Content-Length"] == str(len(resp.data))


def test_html_without_marker_kept_as_is(client, monkeypatch):
    html = b"<html><body>hello</body></html>"
    _stub_send(
        monkeypatch,
        _FakeUpstream(headers={"Content-Type": "text/html"}, chunks=[html]),
    )
    resp = client.get("/login")
    assert resp.data == html


def test_json_passthrough_keeps_content_length(client, monkeypatch):
    body = b'{"ok":true}'
    _stub_send(
        monkeypatch,
        _FakeUpstream(
            headers={"Content-Type": "application/json", "Content-Length": "11"},
            chunks=[body],
        ),
    )
    resp = client.get("/api/budget/balance")
    assert resp.data == body
    assert resp.headers["Content-Length"] == "11"


def test_encoded_response_drops_length_headers(client, monkeypatch):
    body = b'{"ok":true}'
    _stub_send(
        monkeypatch,
        _FakeUpstream(
            headers={
                "Content-Type": "application/json",
                "Content-Encoding": "gzip",
                "Content-Length": "999",
            },
            chunks=[body],
        ),
    )
    resp = client.get("/api/budget/balance")
    assert resp.data == body
    assert "Content-Encoding" not in resp.headers
    assert "Content-Length" not in resp.headers


def test_location_rewritten_to_relay_base(client, monkeypatch):
    monkeypatch.setenv("RELAY_BASE_URL", "https://relay.example.com")
    _stub_send(
        monkeypatch,
        _FakeUpstream(
            status=302,
            headers={"Location": "https://lthub.vercel.app/login"},
            chunks=[],
        ),
    )
    resp = client.get("/old-page")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "https://relay.example.com/login"


def test_external_location_untouched(client, monkeypatch):
    _stub_send(
        monkeypatch,
        _FakeUpstream(
            status=302,
            headers={"Location": "https://example.com/x"},
            chunks=[],
        ),
    )
    resp = client.get("/somewhere")
    assert resp.headers["Location"] == "https://example.com/x"


def test_upstream_timeout_returns_502(client, monkeypatch):
    calls = _stub_send(monkeypatch, error=requests_lib.Timeout("boom"))
    resp = client.get("/any")
    assert resp.status_code == 502
    assert resp.get_json() == {"error": "upstream_unavailable"}
    assert len(calls) == 1


def test_head_preserves_content_length(client, monkeypatch):
    fake = _FakeUpstream(
        headers={"Content-Type": "text/html", "Content-Length": "12345"},
        chunks=[],
    )
    _stub_send(monkeypatch, fake)
    resp = client.head("/")
    assert resp.status_code == 200
    assert resp.headers["Content-Length"] == "12345"
    assert resp.data == b""
    assert fake.closed


def test_set_cookie_passthrough(client, monkeypatch):
    _stub_send(
        monkeypatch,
        _FakeUpstream(
            headers={"Set-Cookie": "session=abc; Path=/", "Content-Type": "text/plain"},
            chunks=[b"ok"],
        ),
    )
    resp = client.get("/some")
    assert "session=abc" in resp.headers.get("Set-Cookie", "")
