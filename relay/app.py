"""Reverse relay: RF-accessible front door for the Vercel-hosted apps.

Deployed on Render (free tier). The browser talks to this service, which
transparently forwards every request to Vercel and streams the response
back. This exists because ``*.vercel.app`` (and ``huggingface.co``,
``workers.dev``) are unreachable from Russian networks while
``onrender.com`` is not.

Routes:
- ``/health`` - local liveness only (Render health check + watchdog warm
  ping that keeps the free instance from sleeping);
- ``/api/music`` and ``/api/music/<path>`` - audio service
  (``audioservice.vercel.app``);
- everything else - main upstream (``lthub.vercel.app``).

HTML responses get one surgical rewrite: ``MUSIC_API_BASE="..."`` becomes
``MUSIC_API_BASE=""`` so the music page calls ``/api/music/*`` on the same
origin (the relay), which routes it to the audio upstream. The Vercel
environment stays untouched.

Environment:
- ``RELAY_MAIN_URL``  - main upstream (default ``https://lthub.vercel.app``);
- ``RELAY_AUDIO_URL`` - audio upstream (default ``https://audioservice.vercel.app``);
- ``RELAY_BASE_URL``  - public base of the relay itself (default: current
  request root); used when rewriting absolute redirect targets.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterator

import requests
from flask import Flask, Response, jsonify, request
from werkzeug.datastructures import Headers

MAIN_UPSTREAM = os.environ.get(
    "RELAY_MAIN_URL", "https://lthub.vercel.app"
).rstrip("/")
AUDIO_UPSTREAM = os.environ.get(
    "RELAY_AUDIO_URL", "https://audioservice.vercel.app"
).rstrip("/")

UPSTREAM_TIMEOUT = (10.0, 120.0)
CHUNK_SIZE = 64 * 1024
RELAY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})

HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)
# Управляются нами: requests декодирует тело, длину выставляем сами,
# accept-encoding принудительно identity, host берётся из URL апстрима.
_MANAGED_REQUEST = frozenset(
    {"host", "content-length", "content-encoding", "accept-encoding"}
)

_MUSIC_BASE_RE = re.compile(rb'MUSIC_API_BASE\s*=\s*"[^"]*"')
_MUSIC_BASE_REPLACEMENT = b'MUSIC_API_BASE=""'

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


def _send(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    params: list[tuple[str, str]],
    data: bytes | None,
) -> requests.Response:
    """Единственная точка вызова апстрима — тесты подменяют именно её."""
    return requests.request(
        method,
        url,
        headers=headers,
        params=params or None,
        data=data,
        stream=True,
        timeout=UPSTREAM_TIMEOUT,
        allow_redirects=False,
    )


def _client_chain() -> str:
    incoming = request.headers.get("X-Forwarded-For", "").strip()
    peer = request.remote_addr or ""
    return ", ".join(part for part in (incoming, peer) if part)


def _request_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in request.headers:
        low = name.lower()
        if low in HOP_BY_HOP or low in _MANAGED_REQUEST:
            continue
        headers[name] = value
    headers["Accept-Encoding"] = "identity"
    headers["X-Forwarded-For"] = _client_chain()
    headers["X-Forwarded-Proto"] = "https"
    headers["X-Forwarded-Host"] = request.host
    return headers


def _relay_base() -> str:
    return (os.environ.get("RELAY_BASE_URL") or request.url_root).rstrip("/")


def _rewrite_location(location: str) -> str:
    for upstream in (MAIN_UPSTREAM, AUDIO_UPSTREAM):
        if location.startswith(upstream):
            return _relay_base() + location[len(upstream):]
    return location


def _collect_response(
    upstream_resp: requests.Response,
) -> tuple[Headers, bool, int | None]:
    """Заголовки апстрима для браузера: (headers, had_encoding, content_length)."""
    out = Headers()
    had_encoding = False
    content_length: int | None = None
    cookies: list[str] = []
    for name, value in upstream_resp.headers.items():
        low = name.lower()
        if low in HOP_BY_HOP:
            continue
        if low == "content-length":
            if value.isdigit():
                content_length = int(value)
            continue
        if low == "content-encoding":
            had_encoding = value.strip().lower() not in ("", "identity")
            continue
        if low == "set-cookie":
            cookies.append(value)
            continue
        if low == "location" and value:
            value = _rewrite_location(value)
        out.add(name, value)
    # requests схлопывает повторяющие Set-Cookie — достаём оригинал из urllib3.
    raw_headers = getattr(getattr(upstream_resp, "raw", None), "headers", None)
    if raw_headers is not None and hasattr(raw_headers, "getlist"):
        real_cookies = raw_headers.getlist("Set-Cookie")
        if real_cookies:
            cookies = list(real_cookies)
    for cookie in cookies:
        out.add("Set-Cookie", cookie)
    return out, had_encoding, content_length


def _relay(upstream: str, path: str) -> Response | tuple:
    url = f"{upstream}/{path.lstrip('/')}" if path else f"{upstream}/"
    params = list(request.args.items(multi=True))
    data = request.get_data(cache=False) if request.method in BODY_METHODS else None

    try:
        upstream_resp = _send(
            request.method,
            url,
            headers=_request_headers(),
            params=params,
            data=data,
        )
    except requests.RequestException as exc:
        app.logger.warning("upstream unavailable: %s", exc.__class__.__name__)
        return jsonify(error="upstream_unavailable"), 502

    out_headers, had_encoding, content_length = _collect_response(upstream_resp)
    status = upstream_resp.status_code
    content_type = upstream_resp.headers.get("Content-Type", "")

    if request.method == "HEAD":
        if content_length is not None and not had_encoding:
            out_headers["Content-Length"] = str(content_length)
        upstream_resp.close()
        return Response(status=status, headers=out_headers)

    if "text/html" in content_type.lower():
        body = b"".join(upstream_resp.iter_content(CHUNK_SIZE))
        upstream_resp.close()
        body = _MUSIC_BASE_RE.sub(_MUSIC_BASE_REPLACEMENT, body)
        out_headers["Content-Length"] = str(len(body))
        return Response(body, status=status, headers=out_headers)

    if content_length is not None and not had_encoding:
        out_headers["Content-Length"] = str(content_length)

    def stream() -> Iterator[bytes]:
        try:
            yield from upstream_resp.iter_content(CHUNK_SIZE)
        finally:
            upstream_resp.close()

    return Response(stream(), status=status, headers=out_headers)


@app.route("/health", methods=["GET", "HEAD"])
def health() -> Response:
    return jsonify(status="ok")


@app.route("/api/music", defaults={"path": ""}, methods=RELAY_METHODS)
@app.route("/api/music/<path:path>", methods=RELAY_METHODS)
def relay_audio(path: str) -> Response:
    return _relay(AUDIO_UPSTREAM, f"api/music/{path}" if path else "")


@app.route("/", defaults={"path": ""}, methods=RELAY_METHODS)
@app.route("/<path:path>", methods=RELAY_METHODS)
def relay_main(path: str) -> Response:
    return _relay(MAIN_UPSTREAM, path)
