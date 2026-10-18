"""Внешний прокси туннеля: ``http``, ``socks5`` и ``socks5h`` без зависимостей.

Зачем отдельный модуль: у машины почти всегда настроен системный прокси
(реестр Windows, ``HTTP_PROXY``/``HTTPS_PROXY``), и он может быть мёртвым -
например, ``127.0.0.1:10801`` от выключенного VPN, - либо указывать на сам
туннель, который ещё не поднят. Раньше все запросы туннеля шли через опенер по
умолчанию и наследовали такой прокси, поэтому запуск висел на ровном месте.

Теперь по умолчанию всё идёт **напрямую** (``ProxyHandler({})``), а внешний
прокси учитывается только если задан явно:

* флаг ``--proxy`` в CLI,
* переменная окружения ``LTHUB_TUNNEL_PROXY``,
* поле ``"proxy"`` в ``sources.local.json``.

Поддержаны ``http`` (через штатный ``ProxyHandler``) и ``socks5``/``socks5h``
(собственный CONNECT, только stdlib - без PySocks). ``socks5h`` резолвит имя на
стороне прокси, ``socks5`` - локально. SOCKS пригодится и для пробы нод: если
напрямую до них не достучаться, задержку можно померить через прокси.
"""

from __future__ import annotations

import http.client
import ipaddress
import os
import socket
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

ENV_VAR = "LTHUB_TUNNEL_PROXY"
_HTTP_SCHEME = "http"
_SOCKS_SCHEMES = {"socks5", "socks5h"}
_DEFAULT_HTTP_PORT = 8080
_DEFAULT_SOCKS_PORT = 1080


@dataclass(frozen=True)
class ProxySpec:
    """Разобранный адрес внешнего прокси."""

    scheme: str
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def url(self) -> str:
        auth = f"{self.username}:{self.password}@" if self.username else ""
        return f"{self.scheme}://{auth}{self.host}:{self.port}"

    @property
    def is_socks(self) -> bool:
        return self.scheme in _SOCKS_SCHEMES


def parse_proxy(value: str | None) -> ProxySpec | None:
    """Разобрать адрес прокси. ``None``/пусто -> ``None`` (идти напрямую)."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if "://" not in text:
        # «127.0.0.1:2080» без схемы - это почти всегда HTTP-прокси.
        text = f"{_HTTP_SCHEME}://{text}"
    parsed = urlsplit(text)
    scheme = (parsed.scheme or _HTTP_SCHEME).lower()
    if scheme not in {_HTTP_SCHEME, *_SOCKS_SCHEMES}:
        raise ValueError(
            f"Прокси {value!r}: схема {scheme!r} не поддержана (нужны http, socks5, socks5h)"
        )
    if not parsed.hostname:
        raise ValueError(f"Прокси {value!r}: не указан хост")
    default_port = _DEFAULT_SOCKS_PORT if scheme in _SOCKS_SCHEMES else _DEFAULT_HTTP_PORT
    return ProxySpec(
        scheme=scheme,
        host=parsed.hostname,
        port=parsed.port or default_port,
        username=parsed.username or "",
        password=parsed.password or "",
    )


def resolve_proxy(
    explicit: str | None = None,
    *,
    config_value: str | None = None,
    env: Mapping[str, str] | None = None,
) -> ProxySpec | None:
    """Выбрать прокси по приоритету: CLI > переменная окружения > конфиг."""
    environment = os.environ if env is None else env
    for raw in (explicit, environment.get(ENV_VAR), config_value):
        if raw and raw.strip():
            return parse_proxy(raw)
    return None


def is_tcp_capable(proxy: ProxySpec | None) -> bool:
    """Умеет ли прокси прокидывать произвольный TCP. Только SOCKS5."""
    return proxy is not None and proxy.is_socks


# --- SOCKS5 (RFC 1928 + RFC 1929) ------------------------------------------


def _recv_exact(sock: socket.socket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise OSError("прокси закрыл соединение")
        data.extend(chunk)
    return bytes(data)


def _socks_greeting(sock: socket.socket, proxy: ProxySpec) -> None:
    methods = bytes([0x00, 0x02]) if proxy.username else bytes([0x00])
    sock.sendall(bytes([0x05, len(methods)]) + methods)
    version, method = _recv_exact(sock, 2)
    if version != 0x05:
        raise OSError("прокси ответил не по протоколу SOCKS5")
    if method == 0x00:
        return
    if method == 0x02 and proxy.username:
        _socks_auth(sock, proxy)
        return
    raise OSError("прокси не принял ни один способ входа")


def _socks_auth(sock: socket.socket, proxy: ProxySpec) -> None:
    user = proxy.username.encode("utf-8")
    password = proxy.password.encode("utf-8")
    sock.sendall(bytes([0x01, len(user)]) + user + bytes([len(password)]) + password)
    _version, status = _recv_exact(sock, 2)
    if status != 0x00:
        raise OSError("неверный логин или пароль")


def _socks_address(host: str, remote_dns: bool) -> bytes:
    try:
        packed = ipaddress.ip_address(host).packed
    except ValueError:
        pass
    else:
        return (b"\x01" if len(packed) == 4 else b"\x04") + packed
    if not remote_dns:
        host = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)[0][4][0]
        packed = ipaddress.ip_address(host).packed
        return (b"\x01" if len(packed) == 4 else b"\x04") + packed
    try:
        name = host.encode("idna")
    except UnicodeError:
        name = host.encode("utf-8")
    return bytes([0x03, len(name)]) + name


def _socks_request(sock: socket.socket, host: str, port: int, remote_dns: bool) -> None:
    sock.sendall(
        b"\x05\x01\x00" + _socks_address(host, remote_dns) + port.to_bytes(2, "big")
    )
    head = _recv_exact(sock, 4)
    if head[1] != 0x00:
        raise OSError(f"CONNECT отклонён (код {head[1]})")
    atyp = head[3]
    if atyp == 0x01:
        _recv_exact(sock, 4)
    elif atyp == 0x04:
        _recv_exact(sock, 16)
    elif atyp == 0x03:
        _recv_exact(sock, _recv_exact(sock, 1)[0])
    _recv_exact(sock, 2)  # порт назначения


def socks5_connect(
    proxy: ProxySpec, host: str, port: int, timeout: float
) -> socket.socket:
    """TCP-соединение с ``host:port`` через SOCKS5. Сокет уже подключён."""
    if not proxy.is_socks:
        raise ValueError("socks5_connect вызван без SOCKS-прокси")
    sock = socket.create_connection((proxy.host, proxy.port), timeout=timeout)
    try:
        sock.settimeout(timeout)
        _socks_greeting(sock, proxy)
        _socks_request(sock, host, port, remote_dns=proxy.scheme == "socks5h")
    except OSError:
        sock.close()
        raise
    return sock


# --- HTTP поверх SOCKS5 ----------------------------------------------------


class _SocksHTTPConnection(http.client.HTTPConnection):
    """``HTTPConnection``, который поднимает TCP через SOCKS5."""

    def __init__(self, *args, proxy: ProxySpec, **kwargs):
        super().__init__(*args, **kwargs)
        self._socks = proxy

    def connect(self) -> None:
        self.sock = socks5_connect(self._socks, self.host, self.port, self.timeout)


class _SocksHTTPSConnection(http.client.HTTPSConnection):
    """То же для HTTPS: сначала SOCKS5, затем штатный TLS-хендшейк."""

    def __init__(self, *args, proxy: ProxySpec, **kwargs):
        super().__init__(*args, **kwargs)
        self._socks = proxy

    def connect(self) -> None:
        raw = socks5_connect(self._socks, self.host, self.port, self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class _Socks5Handler(urllib.request.HTTPHandler, urllib.request.HTTPSHandler):
    """Пускает ``http`` и ``https`` через SOCKS5-прокси."""

    def __init__(self, proxy: ProxySpec):
        urllib.request.HTTPHandler.__init__(self)
        urllib.request.HTTPSHandler.__init__(self)
        self._socks = proxy

    def http_open(self, req):
        return self.do_open(_SocksHTTPConnection, req, proxy=self._socks)

    def https_open(self, req):
        return self.do_open(
            _SocksHTTPSConnection, req, context=self._context, proxy=self._socks
        )


def _opener(proxy: ProxySpec | None):
    """Опенер под конкретный прокси. ``None`` -> строго напрямую."""
    # Явный пустой ProxyHandler ещё и подавляет системный прокси: без него
    # build_opener добавил бы ProxyHandler() из реестра/переменных окружения.
    direct = urllib.request.ProxyHandler({})
    if proxy is None:
        return urllib.request.build_opener(direct)
    if proxy.scheme == _HTTP_SCHEME:
        url = proxy.url
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": url, "https": url})
        )
    return urllib.request.build_opener(direct, _Socks5Handler(proxy))


def open_url(
    url: str,
    *,
    proxy: ProxySpec | None = None,
    timeout: float = 30,
    headers: Mapping[str, str] | None = None,
):
    """Открыть URL, честно управляя прокси.

    ``proxy=None`` - прямое соединение, даже если в системе/env прописан прокси.
    """
    request = urllib.request.Request(url, headers=dict(headers or {}))
    return _opener(proxy).open(request, timeout=timeout)
