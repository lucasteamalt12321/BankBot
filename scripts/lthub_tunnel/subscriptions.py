"""Загрузка VPN-подписок и их разбор в список нод.

Подписки встречаются в трёх видах:

* base64 от ``vless://...`` строк (классический subscription-ответ);
* «голый» текст со ссылками построчно - так отдают некоторые генераторы
  случайных подписок, вместе с заголовками вида ``#profile-title``;
* base64 cURL-подобными ``clash://`` ссылками (такие пропускаем).

Источники проверяются по очереди и молча пропускаются, если не поднялись:
достаточно одного рабочего. Частые причины: сертификат выдан не на тот хост
(``CERTIFICATE_VERIFY_FAILED``) либо сервер не отвечает по IPv4.
"""

from __future__ import annotations

import base64
import binascii
import re
import ssl
from collections.abc import Iterable
from dataclasses import replace
from urllib.error import URLError
from urllib.request import Request, urlopen

from scripts.lthub_tunnel.nodes import Node, parse_trojan, parse_vless

# Подписки отдают разное содержимое в зависимости от User-Agent.
# Первым идёт sing-box: у него самый чистый base64-ответ.
USER_AGENTS = (
    "sing-box",
    "Clash.Meta",
    "v2rayN/6.23.4",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
)

_LINK_RE = re.compile(r"^\s*(vless|trojan)://\S+", re.I)
# Считаем и чужие схемы (vmess, ss, hy2) - они попадают в «мусор» честно.
_ANY_LINK_RE = re.compile(r"^\s*[a-z][a-z0-9+.\-]*://\S+", re.I)
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/\-_\s]+={0,2}$")


class SubscriptionError(RuntimeError):
    """Подписка недоступна или ответ не похож на список нод."""


def fetch(url: str, timeout: int = 30, user_agent: str = USER_AGENTS[0]) -> str:
    """Скачать подписку, при неудаче перебирая User-Agent."""
    last_error: Exception | None = None
    agents = (user_agent,) if user_agent != USER_AGENTS[0] else USER_AGENTS
    for agent in agents:
        request = Request(
            url,
            headers={"User-Agent": agent, "Accept": "*/*", "Accept-Encoding": "identity"},
        )
        try:
            with urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
                return response.read().decode("utf-8", "replace")
        except (URLError, OSError, ValueError) as exc:
            last_error = exc
    raise SubscriptionError(f"{url}: {last_error}") from last_error


def decode_body(text: str) -> str:
    """Распаковать base64-тело подписки; «голый» текст вернуть как есть."""
    if _LINK_RE.search(text):
        return text
    compact = "".join(text.split())
    if not compact or not _BASE64_RE.match(compact):
        return text
    padded = compact + "=" * (-len(compact) % 4)
    try:
        decoded = base64.b64decode(padded.replace("-", "+").replace("_", "/")).decode("utf-8", "replace")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return text
    return decoded if "://" in decoded else text


def parse_subscription(text: str) -> tuple[list[Node], dict[str, int]]:
    """Разобрать тело подписки. Возвращает (ноды, счётчики)."""
    nodes: list[Node] = []
    stats = {"total": 0, "parsed": 0, "skipped": 0}
    for line in decode_body(text).splitlines():
        if not _ANY_LINK_RE.match(line):
            continue
        stats["total"] += 1
        uri = line.strip()
        if uri.lower().startswith("vless://"):
            node = parse_vless(uri)
        elif uri.lower().startswith("trojan://"):
            node = parse_trojan(uri)
        else:
            node = None
        if node is None:
            stats["skipped"] += 1
            continue
        node = _with_tag(node, len(nodes))
        nodes.append(node)
        stats["parsed"] += 1
    return nodes, stats


def _with_tag(node: Node, index: int) -> Node:
    """Присвоить уникальный тег: часть подписок дублирует сервер:порт."""
    return replace(node, tag=f"n{index}")


def merge(nodes: Iterable[Node]) -> list[Node]:
    """Свести ноды из нескольких подписок и перенумеровать теги."""
    merged: list[Node] = []
    seen: set[tuple] = set()
    for node in nodes:
        key = (node.protocol, node.server, node.port, node.uuid or node.password, node.short_id)
        if key in seen:
            continue
        seen.add(key)
        merged.append(_with_tag(node, len(merged)))
    return merged


def load_all(urls: Iterable[str], timeout: int = 30, verbose: bool = True) -> list[Node]:
    """Скачать все подписки и объединить. Недоступные источники пропускаются."""
    nodes: list[Node] = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            body = fetch(url, timeout=timeout)
        except SubscriptionError as exc:
            if verbose:
                print(f"[skip] {exc}")
            continue
        parsed, stats = parse_subscription(body)
        if verbose:
            print(f"[ok]   {url} -> ссылок {stats['total']}, разобрано {stats['parsed']}, мусор {stats['skipped']}")
        nodes.extend(parsed)
    merged = merge(nodes)
    if not merged:
        raise SubscriptionError("ни одна подписка не вернула ни одной ноды")
    return merged