#!/usr/bin/env python3
"""HF startup wrapper with optional sing-box proxy.

If ``VPN_SUBSCRIPTION_URL`` is provided, the script converts a VLESS/sing-box
subscription into a local mixed proxy on ``127.0.0.1:1080`` and then starts
``run_bot.py`` with ``PROXY_URL`` pointing to that proxy.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROXY_HOST = "127.0.0.1"
PROXY_PORT = 1080
CONFIG_PATH = Path("/tmp/sing-box/config.json")


def _decode_subscription(raw: bytes) -> str:
    """Decode plain or base64 subscription payload."""
    text = raw.decode("utf-8", errors="ignore").strip()
    if text.startswith("{") or "vless://" in text:
        return text

    padded = text + "=" * (-len(text) % 4)
    try:
        return base64.b64decode(padded).decode("utf-8", errors="ignore").strip()
    except Exception:
        return text


def _fetch_subscription(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BankBot-HF/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return _decode_subscription(response.read())


def _first_vless_uri(subscription_text: str) -> str:
    for line in subscription_text.replace("\r", "\n").split("\n"):
        line = line.strip()
        if line.startswith("vless://"):
            return line
    raise ValueError("VPN subscription does not contain a supported vless:// node")


def _single_value(query: dict[str, list[str]], key: str, default: str = "") -> str:
    values = query.get(key)
    return values[0] if values else default


def _vless_outbound(uri: str, *, tag: str = "proxy") -> dict[str, Any]:
    parsed = urllib.parse.urlparse(uri)
    query = urllib.parse.parse_qs(parsed.query)

    server = parsed.hostname
    port = parsed.port
    uuid = parsed.username
    if not server or not port or not uuid:
        raise ValueError("VLESS node is missing server, port, or uuid")

    security = _single_value(query, "security", "tls")
    transport_type = _single_value(query, "type", "tcp")
    if transport_type in {"xhttp", "splithttp"}:
        raise ValueError(f"Unsupported VLESS transport for sing-box runtime: {transport_type}")

    outbound: dict[str, Any] = {
        "type": "vless",
        "tag": tag,
        "server": server,
        "server_port": port,
        "uuid": uuid,
    }

    flow = _single_value(query, "flow")
    if flow:
        outbound["flow"] = flow

    if security in {"tls", "reality"}:
        tls: dict[str, Any] = {
            "enabled": True,
            "server_name": _single_value(query, "sni", server),
            "utls": {
                "enabled": True,
                "fingerprint": _single_value(query, "fp", "chrome"),
            },
        }
        if security == "reality":
            public_key = _single_value(query, "pbk")
            if not public_key:
                raise ValueError("Reality VLESS node is missing pbk public key")
            reality: dict[str, Any] = {"enabled": True, "public_key": public_key}
            short_id = _single_value(query, "sid")
            if short_id:
                reality["short_id"] = short_id
            tls["reality"] = reality
        outbound["tls"] = tls

    if transport_type == "grpc":
        outbound["transport"] = {
            "type": "grpc",
            "service_name": _single_value(query, "serviceName"),
        }
    elif transport_type == "ws":
        outbound["transport"] = {
            "type": "ws",
            "path": _single_value(query, "path", "/"),
            "headers": {"Host": _single_value(query, "host", server)},
        }

    return outbound


def _build_config(subscription_text: str) -> dict[str, Any]:
    if subscription_text.startswith("{"):
        config = json.loads(subscription_text)
        config["inbounds"] = [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": PROXY_HOST,
                "listen_port": PROXY_PORT,
            }
        ]
        config.setdefault("route", {})["final"] = _first_proxy_tag(config.get("outbounds", []))
        return config

    proxy_outbounds = _supported_vless_outbounds(subscription_text)
    if not proxy_outbounds:
        raise ValueError("VPN subscription has no supported VLESS nodes")

    final_tag = "proxy"
    outbounds = proxy_outbounds + [{"type": "direct", "tag": "direct"}]
    if len(proxy_outbounds) > 1:
        outbounds.append(
            {
                "type": "urltest",
                "tag": "proxy",
                "outbounds": [outbound["tag"] for outbound in proxy_outbounds],
                "url": "https://www.gstatic.com/generate_204",
                "interval": "10m",
                "tolerance": 50,
            }
        )
    else:
        proxy_outbounds[0]["tag"] = final_tag

    return {
        "log": {"level": "warn"},
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": PROXY_HOST,
                "listen_port": PROXY_PORT,
            }
        ],
        "outbounds": outbounds,
        "route": {"final": final_tag},
    }


def _supported_vless_outbounds(subscription_text: str) -> list[dict[str, Any]]:
    """Return all VLESS nodes supported by the lightweight HF generator."""
    outbounds: list[dict[str, Any]] = []
    lines = [line.strip() for line in subscription_text.replace("\r", "\n").split("\n")]
    for line in lines:
        if not line.startswith("vless://"):
            continue
        node_number = len(outbounds) + 1
        try:
            outbounds.append(_vless_outbound(line, tag=f"proxy-{node_number}"))
        except Exception as exc:
            print(f"[VPN] Skipping unsupported node: {exc}")
    print(f"[VPN] Supported proxy nodes: {len(outbounds)}")
    return outbounds


def _first_proxy_tag(outbounds: list[dict[str, Any]]) -> str:
    for outbound in outbounds:
        tag = outbound.get("tag")
        if tag and outbound.get("type") not in {"direct", "block", "dns"}:
            return tag
    return outbounds[0].get("tag", "proxy") if outbounds else "proxy"


def _wait_for_proxy(timeout: int = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=1):
                return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError("sing-box proxy did not become ready")


def _start_sing_box() -> subprocess.Popen:
    subscription_url = os.environ.get("VPN_SUBSCRIPTION_URL", "").strip()
    if not subscription_url:
        raise ValueError("VPN_SUBSCRIPTION_URL is empty")

    print("[VPN] Loading VPN subscription")
    subscription_text = _fetch_subscription(subscription_url)
    config = _build_config(subscription_text)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[VPN] Starting sing-box local proxy")
    process = subprocess.Popen(["sing-box", "run", "-c", str(CONFIG_PATH)])
    _wait_for_proxy()
    print(f"[VPN] Local proxy ready at http://{PROXY_HOST}:{PROXY_PORT}")
    return process


def main() -> None:
    if os.environ.get("VPN_SUBSCRIPTION_URL", "").strip():
        try:
            _start_sing_box()
            os.environ["PROXY_URL"] = f"http://{PROXY_HOST}:{PROXY_PORT}"
            os.environ["TELEGRAM_BASE_URL"] = "https://api.telegram.org/bot/"
        except Exception as exc:
            print(f"[VPN] Failed to start VPN proxy: {exc}")
            raise

    os.execvpe(sys.executable, [sys.executable, "run_bot.py"], os.environ)


if __name__ == "__main__":
    main()
