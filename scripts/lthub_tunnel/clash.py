"""Экспорт нод в Clash / Mihomo YAML - конфиг для раздачи пользователям бота.

Android-вариант: пользователь ставит любой клиент (Mihomo, Clash Meta GUI)
и импортирует файл, либо открывает ссылку-подписку. Свой APK не нужен.

Формат ``proxies`` повторяет подписку, ``proxy-groups`` даёт:
``auto`` - url-test по нашему health-эндпоинту, ``manual`` - ручной выбор.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import yaml

from scripts.lthub_tunnel.nodes import Node, unsupported_reason
from scripts.lthub_tunnel.sbconfig import DEFAULT_PROBE_URL


def node_to_clash(node: Node) -> dict | None:
    """Proxy-словарь Clash для ноды либо None, если её sing-box тоже не берёт."""
    if unsupported_reason(node):
        return None

    proxy: dict = {
        "name": f"{node.tag} {node.label}"[:80],
        "type": node.protocol,
        "server": node.server,
        "port": node.port,
        "udp": True,
    }
    if node.protocol == "vless":
        proxy["uuid"] = node.uuid
    else:
        proxy["password"] = node.password

    if node.security in {"tls", "reality"}:
        proxy["tls"] = True
        if node.sni:
            proxy["servername"] = node.sni
        if node.allow_insecure:
            proxy["skip-cert-verify"] = True
        if node.alpn:
            proxy["alpn"] = list(node.alpn)
        if node.fingerprint:
            proxy["client-fingerprint"] = node.fingerprint
        if node.security == "reality":
            proxy["reality-opts"] = {
                "public-key": node.public_key,
                "short-id": node.short_id or "",
            }
    if node.flow and node.network == "tcp":
        proxy["flow"] = node.flow

    if node.network == "ws":
        proxy["network"] = "ws"
        proxy["ws-opts"] = {
            "path": node.path or "/",
            **({"headers": {"Host": node.host}} if node.host else {}),
        }
    elif node.network == "grpc":
        proxy["network"] = "grpc"
        proxy["grpc-opts"] = {"grpc-service-name": node.service_name}
    elif node.network == "http":
        proxy["network"] = "http"
        proxy["http-opts"] = {
            "path": [node.path or "/"],
            **({"headers": {"Host": [node.host]}} if node.host else {}),
        }
    elif node.network == "httpupgrade":
        proxy["network"] = "ws"
        proxy["ws-opts"] = {
            "path": node.path or "/",
            "headers": {"Host": node.host} if node.host else {},
            "v2ray-http-upgrade": True,
        }
    return proxy


def build_clash(
    nodes: Sequence[Node],
    *,
    probe_url: str = DEFAULT_PROBE_URL,
    probe_interval: int = 300,
) -> tuple[dict, list[tuple[Node, str]]]:
    """Вернуть (конфиг Clash, отброшенные ноды с причинами)."""
    proxies: list[dict] = []
    rejected: list[tuple[Node, str]] = []
    for node in nodes:
        proxy = node_to_clash(node)
        if proxy is None:
            rejected.append((node, unsupported_reason(node)))
            continue
        proxies.append(proxy)

    if not proxies:
        raise ValueError("после фильтрации не осталось ни одной рабочей ноды")

    names = [proxy["name"] for proxy in proxies]
    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": proxies,
        "proxy-groups": [
            {
                "name": "auto",
                "type": "url-test",
                "proxies": names,
                "url": probe_url,
                "interval": probe_interval,
                "tolerance": 100,
            },
            {"name": "manual", "type": "select", "proxies": ["auto", *names]},
        ],
        "rules": ["MATCH,auto"],
    }, rejected


def dump_clash(config: dict, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=4096),
        encoding="utf-8",
    )
    return target