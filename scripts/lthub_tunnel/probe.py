"""Пинг нод подписки: отсеять мёртвые и отсортировать по скорости.

Отбор двухступенчатый, и разница принципиальна:

1. **Здесь** меряется TCP-коннект к ``server:port`` (+ TLS-хендшейк с SNI, если
   нода на TLS). Это дешёвый параллельный фильтр: он отсекает мёртвые адреса за
   секунды, не поднимая ни одного туннеля, и сортирует выжившие.
2. **Реальную сквозную задержку** меряет сам sing-box в группе ``urltest`` -
   уже через туннель, уже с настоящим протоколом. Он же держит победителя,
   пока прокси жив, и уходит на другую ноду, когда текущая умирает.

Одного TCP-пинга недостаточно: адрес может принимать соединения, а прокси
через него - нет (например, за CDN с неверным SNI). Поэтому результат здесь -
это фильтр и порядок, а окончательный выбор всё равно за ``urltest``.

Модуль ходит в сеть, но не трогает учётные данные нод: он не подключается к
самому протоколу и не отправляет ничего, кроме TLS ClientHello.
"""

from __future__ import annotations

import ipaddress
import socket
import ssl
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from scripts.lthub_tunnel.nodes import Node

# Мёртвые ноды надо отсеивать быстро: 32 потока на ~100 нод - это пара секунд.
DEFAULT_WORKERS = 32
# TLS-хендшейк с кривым сертификатом не должен висеть дольше коннекта.
DEFAULT_TIMEOUT = 3.0
# Сколько самых быстрых нод оставляем в конфиге. Больше десятка смысла нет:
# urltest всё равно замеряет их все, а мёртвые всё равно отсеются.
DEFAULT_TOP = 10


@dataclass(frozen=True)
class PingResult:
    """Результат пинга одной ноды."""

    tag: str
    latency_ms: float = 0.0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _tls_context(verify: bool) -> ssl.SSLContext:
    if verify:
        return ssl.create_default_context()
    # reality и подписи с skip-cert-verify: главное - дойти до хендшейка.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def ping_node(node: Node, *, timeout: float = DEFAULT_TIMEOUT) -> PingResult:
    """Замерить задержку до ``server:port``. Ошибка - в ``PingResult.error``.

    Замеряется коннект и TLS-хендшейк; резолв DNS вынесен за скобки, потому
    что системный кеш делает его время почти случайным.
    """
    try:
        infos = socket.getaddrinfo(node.server, node.port, type=socket.SOCK_STREAM)
    except OSError as exc:
        return PingResult(node.tag, error=f"DNS: {exc.strerror or exc}")

    server_name = node.sni or node.server
    # TLS без SNI не бывает: для адреса-IP хендшейк не проверяем, только коннект.
    use_tls = node.security in {"tls", "reality"} and not _is_ip(server_name)
    verify = not node.allow_insecure

    last = "неизвестная ошибка"
    for family, socktype, proto, _canon, address in infos:
        sock = socket.socket(family, socktype, proto)
        started = time.monotonic()
        try:
            sock.settimeout(timeout)
            sock.connect(address)
            if use_tls:
                with _tls_context(verify).wrap_socket(sock, server_hostname=server_name):
                    pass
            return PingResult(node.tag, latency_ms=(time.monotonic() - started) * 1000)
        except (OSError, ssl.SSLError, ValueError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                sock.close()
            except OSError:
                pass
    return PingResult(node.tag, error=last)


def probe_nodes(
    nodes: Sequence[Node],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    workers: int = DEFAULT_WORKERS,
) -> dict[str, PingResult]:
    """Запинговать ноды параллельно. Ключ - тег ноды."""
    if not nodes:
        return {}
    pool = max(1, min(workers, len(nodes)))
    with ThreadPoolExecutor(max_workers=pool) as executor:
        results = executor.map(lambda node: ping_node(node, timeout=timeout), nodes)
        return {result.tag: result for result in results}


def select_fastest(
    nodes: Sequence[Node],
    results: dict[str, PingResult],
    *,
    top: int = DEFAULT_TOP,
) -> tuple[list[Node], list[PingResult]]:
    """Живые ноды, отсортированные по пингу. Второй элемент - неотвевшие.

    ``top <= 0`` - оставить всех живых. Если пинг не отвечает ни одна нода,
    возвращаются исходные ноды: пинг тут фильтр, а не приговор, и ронять
    конфиг из-за чужих сетевых условий нельзя.
    """
    alive: list[Node] = []
    dead: list[PingResult] = []
    for node in nodes:
        result = results.get(node.tag)
        if result is None or not result.ok:
            dead.append(result or PingResult(node.tag, error="нет результата пинга"))
            continue
        alive.append(node)
    if not alive:
        return list(nodes), dead
    alive.sort(key=lambda node: results[node.tag].latency_ms)
    if top > 0:
        alive = alive[:top]
    return alive, dead


def format_ping_table(
    nodes: Sequence[Node],
    results: dict[str, PingResult],
    *,
    limit: int = 0,
) -> str:
    """Человекочитаемая таблица «пинг / нода», от быстрых к медленным."""
    lines: list[tuple[float, Node]] = []
    dead: list[Node] = []
    for node in nodes:
        result = results.get(node.tag)
        if result is not None and result.ok:
            lines.append((result.latency_ms, node))
        else:
            dead.append(node)
    lines.sort(key=lambda pair: pair[0])
    if limit > 0:
        lines = lines[:limit]

    out = ["Топ нод по TCP/TLS-пингу:"]
    if not lines:
        out.append("  (никто не ответил)")
    for latency, node in lines:
        out.append(f"  {latency:7.0f} мс  {node.tag:>5}  {node.label}")
    if dead:
        out.append(f"Не ответили: {len(dead)}")
    return "\n".join(out)