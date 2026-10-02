"""Разбор VPN-подписок: ``vless://`` и ``trojan://`` -> outbound sing-box.

Модуль не ходит в сеть. Входные строки - ровно то, что отдаёт подписка,
поэтому парсер терпим к мусору: агрегаторы дописывают в ``host`` имя ноды,
оставляют ``mode=gun`` и ``spx``, которых в sing-box нет.

Неподдерживаемое отбрасывается с причиной (``convert``), а не роняет
конфиг целиком - битые ноды в подписке это норма.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote, urlsplit

# Сети, которые умеет sing-box. ``raw`` - это Xrayное имя обычного TCP,
# ``splithttp``/``h2`` - алиасы HTTP/2 транспорта.
_NETWORK_ALIASES = {
    "": "tcp",
    "raw": "tcp",
    "tcp": "tcp",
    "ws": "ws",
    "websocket": "ws",
    "grpc": "grpc",
    "gun": "grpc",
    "http": "http",
    "h2": "http",
    "splithttp": "http",
    "httpupgrade": "httpupgrade",
}

_UNSUPPORTED_NETWORKS = {
    "xhttp": "транспорт xhttp в этой сборке sing-box не используем",
    "quic": "транспорт quic не используем",
    "kcp": "транспорт kcp/mkcp не используем",
}

_REALITY_FLOWS = {"xtls-rprx-vision"}


@dataclass(frozen=True)
class Node:
    """Нормализованная нода подписки."""

    tag: str
    protocol: str
    name: str
    server: str
    port: int
    uuid: str = ""
    password: str = ""
    security: str = "none"
    sni: str = ""
    public_key: str = ""
    short_id: str = ""
    fingerprint: str = ""
    allow_insecure: bool = False
    alpn: tuple[str, ...] = ()
    network: str = "tcp"
    path: str = ""
    host: str = ""
    service_name: str = ""
    permit_without_stream: bool = False
    flow: str = ""
    packet_encoding: str = ""

    @property
    def label(self) -> str:
        """Человекочитаемое имя: как в подписке, иначе по серверу."""
        return self.name or f"{self.protocol}://{self.server}:{self.port}"


def _query(raw: str) -> dict[str, str]:
    """Пары query-параметров с одним значением на ключ, в нижнем регистре."""
    out: dict[str, str] = {}
    for key, value in parse_qsl(raw, keep_blank_values=True):
        out.setdefault(key.lower(), unquote(value))
    return out


def _first(params: dict[str, str], *names: str) -> str:
    for name in names:
        value = params.get(name, "")
        if value:
            return value
    return ""


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def _clean_host(value: str) -> str:
    """Убрать мусор, который агрегаторы пихают в ``host``.

    В реальных подписках встречается ``host=?TELEGRAM@MARAMBASHI_MARAMBASHI`` -
    это скрипт переименования нод дописал имя в поле Host. Для TCP-transport
    поле не используется, для ws/http - использовать его нельзя.
    """
    value = value.strip()
    if not value:
        return ""
    if "?" in value or "@" in value:
        return ""
    return value


def _common(params: dict[str, str], server: str) -> dict:
    """Поля, общие для vless и trojan."""
    security = _first(params, "security").lower()
    public_key = _first(params, "pbk", "publickey")
    if not security and public_key:
        security = "reality"

    sni = _first(params, "sni", "peer", "servername")
    host = _clean_host(_first(params, "host"))
    if not sni:
        sni = host or server

    alpn = tuple(
        part.strip()
        for part in _first(params, "alpn").split(",")
        if part.strip()
    )
    mode = _first(params, "mode").lower()
    # sing-box знает только xudp и packetaddr; Xray-овское "none" не пройдёт.
    packet_encoding = _first(params, "packetencoding", "packet_encoding").lower()
    if packet_encoding not in {"xudp", "packetaddr"}:
        packet_encoding = ""
    return {
        "security": security if security in {"tls", "reality"} else "none",
        "sni": sni,
        "public_key": public_key,
        "short_id": _first(params, "sid", "shortid"),
        "fingerprint": _first(params, "fp", "fingerprint").lower(),
        "allow_insecure": _truthy(_first(params, "insecure", "allowinsecure", "skip-cert-verify")),
        "alpn": alpn,
        "network": _first(params, "type").lower() or "tcp",
        "path": _first(params, "path"),
        "host": host,
        "service_name": _first(params, "servicename", "service_name"),
        "permit_without_stream": mode == "auto",
        "flow": _first(params, "flow"),
        "packet_encoding": packet_encoding,
    }


def _split_authority(uri: str) -> tuple[str, str, int] | None:
    """Достать credential / host / port из ``scheme://cred@host:port?...``."""
    parts = urlsplit(uri.strip())
    if not parts.hostname:
        return None
    credential = unquote(parts.username or "")
    if parts.password:
        credential = f"{credential}:{unquote(parts.password)}"
    try:
        port = int(parts.port or 0)
    except ValueError:
        return None
    if not port:
        return None
    return credential, parts.hostname, port


def parse_vless(uri: str, index: int = 0) -> Node | None:
    """Разобрать ``vless://uuid@host:port?...#name``. None - мусор."""
    if not uri.lower().startswith("vless://"):
        return None
    authority = _split_authority(uri)
    if authority is None:
        return None
    credential, server, port = authority
    if not credential:
        return None

    parts = urlsplit(uri.strip())
    params = _query(parts.query)
    common = _common(params, server)
    return Node(
        tag=f"n{index}",
        protocol="vless",
        name=unquote(parts.fragment),
        server=server,
        port=port,
        uuid=credential,
        **common,
    )


def parse_trojan(uri: str, index: int = 0) -> Node | None:
    """Разобрать ``trojan://password@host:port?...#name``. None - мусор."""
    if not uri.lower().startswith("trojan://"):
        return None
    authority = _split_authority(uri)
    if authority is None:
        return None
    credential, server, port = authority
    if not credential:
        return None

    parts = urlsplit(uri.strip())
    params = _query(parts.query)
    common = _common(params, server)
    # У trojan TLS включается сам по себе,Reality в подписках не встречается.
    common["security"] = "tls" if common["security"] == "none" else common["security"]
    return Node(
        tag=f"n{index}",
        protocol="trojan",
        name=unquote(parts.fragment),
        server=server,
        port=port,
        password=credential,
        **common,
    )


def _transport(node: Node) -> dict:
    """Транспорт sing-box или пустой dict, если транспорт не нужен."""
    if node.network == "ws":
        transport: dict = {"type": "ws", "path": node.path or "/"}
        if node.host:
            transport["headers"] = {"Host": node.host}
        return transport
    if node.network == "grpc":
        transport = {"type": "grpc", "service_name": node.service_name}
        if node.permit_without_stream:
            transport["permit_without_stream"] = True
        return transport
    if node.network == "http":
        transport = {"type": "http", "path": node.path or "/"}
        if node.host:
            transport["host"] = [node.host]
        return transport
    if node.network == "httpupgrade":
        transport = {"type": "httpupgrade", "path": node.path or "/"}
        if node.host:
            transport["host"] = node.host
        return transport
    return {"type": "tcp"}


def _tls_block(node: Node) -> dict:
    tls: dict = {"enabled": True, "server_name": node.sni or node.server}
    if node.allow_insecure:
        tls["insecure"] = True
    if node.alpn:
        tls["alpn"] = list(node.alpn)
    # Reality без uTLS sing-box не принимает: подставляем дефолтный отпечаток.
    fingerprint = node.fingerprint or ("chrome" if node.security == "reality" else "")
    if fingerprint:
        tls["utls"] = {"enabled": True, "fingerprint": fingerprint}
    if node.security == "reality":
        reality: dict = {"enabled": True, "public_key": node.public_key}
        if node.short_id:
            reality["short_id"] = node.short_id
        tls["reality"] = reality
    return tls


def unsupported_reason(node: Node) -> str:
    """Пустая строка - ноду можно собрать; иначе причина отбрасывания."""
    if not node.server or not node.port:
        return "нет адреса или порта"
    if node.protocol == "vless" and not node.uuid:
        return "пустой uuid"
    if node.protocol == "trojan" and not node.password:
        return "пустой пароль"
    if node.network in _UNSUPPORTED_NETWORKS:
        return _UNSUPPORTED_NETWORKS[node.network]
    if node.network not in _NETWORK_ALIASES:
        return f"неизвестный транспорт {node.network!r}"
    if node.security == "reality" and not node.public_key:
        return "reality без public key (pbk)"
    if node.flow and node.flow not in _REALITY_FLOWS:
        return f"неизвестный flow {node.flow!r}"
    return ""


def convert(node: Node) -> tuple[dict | None, str]:
    """Outbound sing-box для ноды. Второй элемент - причина отказа."""
    reason = unsupported_reason(node)
    if reason:
        return None, reason

    network = _NETWORK_ALIASES.get(node.network, "tcp")
    # flow в Xray работает только поверх TCP; на ws/grpc его просто нет.
    flow = node.flow if (node.flow and network == "tcp") else ""

    if node.protocol == "trojan":
        outbound: dict = {
            "type": "trojan",
            "tag": node.tag,
            "server": node.server,
            "server_port": node.port,
            "password": node.password,
        }
    else:
        outbound = {
            "type": "vless",
            "tag": node.tag,
            "server": node.server,
            "server_port": node.port,
            "uuid": node.uuid,
        }
        if flow:
            outbound["flow"] = flow
        if node.packet_encoding:
            outbound["packet_encoding"] = node.packet_encoding

    if node.security in {"tls", "reality"}:
        outbound["tls"] = _tls_block(node)

    # У sing-box transport по умолчанию - голый TCP, и явный "tcp" он не знает.
    transport = _transport(node) if network != "tcp" else {}
    if transport:
        outbound["transport"] = transport
    return outbound, ""