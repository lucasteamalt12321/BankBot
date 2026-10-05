"""Тесты разбора VPN-подписок и сборки конфигов туннеля.

Фикстуры - реальные строки из боевой подписки (агрегаторские ноды), поэтому
проверяются и грязные параметры: ``host=?TELEGRAM@...``, ``type=raw``,
отсутствующий ``fp`` у reality, ``mode=gun``.
"""

from __future__ import annotations

import base64
import json
import ssl
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.lthub_tunnel.clash import build_clash, node_to_clash
from scripts.lthub_tunnel.nodes import (
    Node,
    convert,
    parse_trojan,
    parse_vless,
    unsupported_reason,
)
from scripts.lthub_tunnel.probe import (
    PingResult,
    format_ping_table,
    probe_nodes,
    select_fastest,
)
from scripts.lthub_tunnel.sbconfig import build_config, prune_config, write_nodes_report
from scripts.lthub_tunnel import runner, subscriptions
from scripts.lthub_tunnel.subscriptions import (
    SubscriptionError,
    decode_body,
    fetch,
    merge,
    parse_subscription,
)
from scripts.lthub_tunnel import tunnel
from scripts.lthub_tunnel.tunnel import pick_fastest

# reality + tcp, без fp (sing-box требует uTLS для reality) и с мусором в host
REALITY_TCP = (
    "vless://a18f7c2d-9e45-4b8a-af3c-1d5e7f9c8b2a@83.168.71.216:443"
    "?encryption=none&type=tcp&headerType=none&host=/?TELEGRAM@MARAMBASHI_MARAMBASHI"
    "&security=reality&fp=chrome&sni=ads.x5.ru"
    "&pbk=8h8t5eBWL9oERK7xWHQLFJE5j6sZdgNDQAs3EGnNbho&sid=2f49bccf11150ef2"
    "#AetrisVPN 105"
)

# reality без fp вообще - должен получить дефолтный отпечаток
REALITY_NO_FP = (
    "vless://1c332eae-7e02-4acd-996d-4eb3e652401c@prep.wwwinternetvideo.click:443"
    "?flow=xtls-rprx-vision&fp=&security=reality&sni=yandex.ru&type=tcp"
    "&pbk=uitO9X8t9TplwwYaqwLqh5rfxDh_X8bOBiNuPbzvaEM&encryption=none#243.%20RU"
)

WS_TLS = (
    "vless://bc5ec86c-3e65-4272-994c-59a924c72a68@217.19.122.200:443"
    "?alpn=http%2F1.1&encryption=none&fp=chrome&host=fbsv6.guardora.pro&path=%2Fws"
    "&security=tls&sni=fbsv6.guardora.pro&type=ws#rostunnel"
)

GRPC_REALTITY = (
    "vless://5d16ac22-6eea-426f-b778-6f4c2961faef@176.108.246.58:9889"
    "?type=grpc&security=reality&encryption=none&sni=dl.google.com"
    "&serviceName=grpc-tunnel&fp=firefox&pbk=ycPIUcY6ci2yi7YA_OHc20e4gzxEdJTqpmeShxSuHRU"
)

XHTTP_NODE = (
    "vless://9737cc16-7266-45ce-94d9-6e05a45e0b9c@84.38.181.249:443"
    "?encryption=none&path=%2F&pbk=pyZ0M0nE3aGx2UtCXNhajcneyCF4E8J3zpxhIKkQw0w"
    "&security=reality&sid=6bc02f1c474260c3&sni=open.spotify.com&type=xhttp&fp=ios"
)

TROJAN_NODE = "trojan://hunter2password@example.org:443?security=tls&sni=example.org&type=tcp#trojan"


def _nodes(*uris: str) -> list[Node]:
    """Ноды с уникальными тегами - так же, как их даёт parse_subscription."""
    nodes, _ = parse_subscription("\n".join(uris))
    return nodes


def test_parse_reality_tcp_cleans_garbage_host():
    node = parse_vless(REALITY_TCP)
    assert node is not None
    assert node.protocol == "vless"
    assert node.server == "83.168.71.216"
    assert node.port == 443
    assert node.uuid == "a18f7c2d-9e45-4b8a-af3c-1d5e7f9c8b2a"
    assert node.security == "reality"
    assert node.sni == "ads.x5.ru"
    assert node.short_id == "2f49bccf11150ef2"
    assert node.network == "tcp"
    assert node.flow == ""
    # мусорный host из скрипта переименования не должен попасть в ноду
    assert node.host == ""
    assert node.name == "AetrisVPN 105"


def test_flow_parsed_and_bad_bracket():
    node = parse_vless("vless://a@b.c:443?flow=xtls-rprx-vision#bad%20name")
    assert node is not None
    assert node.flow == "xtls-rprx-vision"
    assert node.name == "bad name"


def test_reality_without_fingerprint_gets_default_utls():
    node = parse_vless(REALITY_NO_FP)
    assert node is not None
    assert node.fingerprint == ""
    outbound, reason = convert(node)
    assert reason == ""
    # sing-box не принимает reality без uTLS
    assert outbound["tls"]["utls"] == {"enabled": True, "fingerprint": "chrome"}
    assert outbound["flow"] == "xtls-rprx-vision"


def test_ws_transport_carries_path_and_host():
    node = parse_vless(WS_TLS)
    assert node is not None
    assert node.network == "ws"
    assert node.path == "/ws"
    assert node.host == "fbsv6.guardora.pro"
    assert node.security == "tls"
    assert node.alpn == ("http/1.1",)
    outbound, _ = convert(node)
    assert outbound["transport"] == {
        "type": "ws",
        "path": "/ws",
        "headers": {"Host": "fbsv6.guardora.pro"},
    }
    assert outbound["tls"]["server_name"] == "fbsv6.guardora.pro"
    assert "reality" not in outbound["tls"]


def test_grpc_mode_auto_allows_non_stream():
    node = parse_vless(GRPC_REALTITY)
    assert node is not None
    assert node.network == "grpc"
    assert node.service_name == "grpc-tunnel"
    outbound, _ = convert(node)
    assert outbound["transport"] == {"type": "grpc", "service_name": "grpc-tunnel"}
    assert "packet_encoding" not in outbound


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("none", ""), ("xudp", "xudp"), ("packetaddr", "packetaddr"), ("", "")],
)
def test_packet_encoding_whitelist(raw, expected):
    """Xray пишет packetEncoding=none - sing-box такое значение не принимает."""
    uri = REALITY_TCP.replace("#AetrisVPN 105", f"&packetEncoding={raw}#AetrisVPN 105")
    node = parse_vless(uri)
    assert node.packet_encoding == expected
    outbound, reason = convert(node)
    assert reason == ""
    assert outbound.get("packet_encoding", "") == expected


def test_tcp_has_no_explicit_transport():
    """Явный transport type=tcp sing-box не знает - он должен отсутствовать."""
    node = parse_vless(REALITY_TCP)
    outbound, _ = convert(node)
    assert "transport" not in outbound


def test_type_raw_is_alias_for_tcp():
    node = parse_vless(REALITY_TCP.replace("type=tcp", "type=raw"))
    assert node is not None
    assert unsupported_reason(node) == ""
    outbound, _ = convert(node)
    assert "transport" not in outbound


def test_xhttp_rejected_with_reason():
    node = parse_vless(XHTTP_NODE)
    assert node is not None
    outbound, reason = convert(node)
    assert outbound is None
    assert "xhttp" in reason


def test_reality_without_public_key_rejected():
    node = parse_vless(XHTTP_NODE.replace("type=xhttp&fp=ios", "type=tcp").replace(
        "&pbk=pyZ0M0nE3aGx2UtCXNhajcneyCF4E8J3zpxhIKkQw0w", ""
    ))
    assert node is not None
    outbound, reason = convert(node)
    assert outbound is None
    assert "public key" in reason


def test_trojan_defaults_to_tls():
    node = parse_trojan(TROJAN_NODE)
    assert node is not None
    assert node.protocol == "trojan"
    assert node.password == "hunter2password"
    assert node.security == "tls"
    outbound, reason = convert(node)
    assert reason == ""
    assert outbound["type"] == "trojan"
    assert outbound["password"] == "hunter2password"


@pytest.mark.parametrize(
    "uri",
    ["", "vless://", "vless://uuid@host", "vmess://eyJhIjoxfQ==", "trojan://@:0#x"],
)
def test_garbage_returns_none(uri):
    assert parse_vless(uri) is None
    assert parse_trojan(uri) is None


def test_decode_body_passes_plain_text_through():
    plain = "#profile-title: x\nvless://a@b.c:443#n\n"
    assert decode_body(plain) is plain


def test_decode_body_unwraps_base64():
    plain = "vless://a@b.c:443#n\ntrojan://p@d.e:443#m\n"
    encoded = base64.b64encode(plain.encode()).decode()
    assert decode_body(encoded) == plain


def test_decode_body_keeps_undecodable():
    assert decode_body("просто текст без ссылок") == "просто текст без ссылок"


def test_parse_subscription_counts_and_ignores_comments():
    body = "\n".join(
        [
            "#profile-title: all_subs",
            "#subscription-userinfo: upload=0; download=0; total=0",
            "",
            REALITY_TCP,
            WS_TLS,
            "vmess://eyJhIjoxfQ==",
        ]
    )
    nodes, stats = parse_subscription(body)
    assert stats == {"total": 3, "parsed": 2, "skipped": 1}
    assert [n.tag for n in nodes] == ["n0", "n1"]


def test_merge_dedups_and_renumbers_tags():
    first = parse_vless(REALITY_TCP)
    duplicate = parse_vless(REALITY_TCP)
    other = parse_vless(WS_TLS)
    merged = merge([first, duplicate, other])
    assert len(merged) == 2
    assert [n.tag for n in merged] == ["n0", "n1"]


def test_build_config_shape_and_probe_url():
    nodes = _nodes(REALITY_TCP, WS_TLS, XHTTP_NODE)
    config, rejected = build_config(nodes, port=2080, probe_url="https://probe.test/204")
    assert config["inbounds"][0]["type"] == "mixed"
    assert config["inbounds"][0]["listen"] == "127.0.0.1"
    assert config["inbounds"][0]["listen_port"] == 2080
    assert config["route"]["final"] == "auto"

    group = config["outbounds"][0]
    assert group["type"] == "urltest"
    assert group["url"] == "https://probe.test/204"
    # xhttp отфильтрован, в группе осталось две ноды
    assert group["outbounds"] == ["n0", "n1"]
    assert [r[0].name for r in rejected] == [""]
    assert config["outbounds"][-1] == {"type": "direct", "tag": "direct"}


def test_build_config_without_usable_nodes_raises():
    node = parse_vless(XHTTP_NODE)
    with pytest.raises(ValueError, match="не осталось"):
        build_config([node])


def test_build_config_cache_file_optional():
    config, _ = build_config([parse_vless(REALITY_TCP)], cache_file="C:/tmp/cache.db")
    assert config["experimental"]["cache_file"]["enabled"] is True
    plain, _ = build_config([parse_vless(REALITY_TCP)])
    assert "experimental" not in plain


def test_prune_config_drops_offending_outbound():
    """sing-box падает целиком на одной плохой ноде - её надо выкинуть.

    Индекс в ошибке - позиция во всём массиве outbounds, где 0 занимает
    группа urltest, поэтому n2 это outbound[3].
    """
    config, _ = build_config(_nodes(REALITY_TCP, WS_TLS, GRPC_REALTITY))
    assert config["outbounds"][0]["outbounds"] == ["n0", "n1", "n2"]

    calls = []

    def fake_check(cfg):
        calls.append(list(cfg["outbounds"][0]["outbounds"]))
        # ругаемся на n2, пока она в группе
        return "initialize outbound[3]: unsupported flow: x" if len(cfg["outbounds"]) > 4 else None

    pruned, removed = prune_config(config, fake_check)
    assert pruned["outbounds"][0]["outbounds"] == ["n0", "n1"]
    assert len(pruned["outbounds"]) == 4  # urltest + 2 ноды + direct
    assert len(removed) == 1
    assert "n2" in removed[0]
    assert "unsupported flow" in removed[0]
    assert calls == [["n0", "n1", "n2"], ["n0", "n1"]]


def test_prune_config_strips_ansi_colors():
    config, _ = build_config(_nodes(REALITY_TCP, WS_TLS))
    error = "\x1b[31mFATAL\x1b[0m[0000] initialize outbound[1]: uTLS is required by reality client"

    def fake_check(cfg):
        return error if len(cfg["outbounds"]) > 3 else None

    pruned, removed = prune_config(config, fake_check)
    assert "\x1b" not in removed[0]
    assert "uTLS is required" in removed[0]
    assert pruned["outbounds"][0]["outbounds"] == ["n1"]


def test_prune_config_raises_on_unparsable_error():
    config, _ = build_config(_nodes(REALITY_TCP))
    with pytest.raises(ValueError, match="не понимает ошибку"):
        prune_config(config, lambda cfg: "FATAL: connection refused")


def test_prune_config_raises_when_group_itself_is_bad():
    config, _ = build_config(_nodes(REALITY_TCP))
    with pytest.raises(ValueError, match="bad urltest"):
        prune_config(config, lambda cfg: "FATAL: initialize outbound[0]: bad urltest")


def test_prune_config_gives_up_after_max_passes():
    config, _ = build_config(_nodes(REALITY_TCP, WS_TLS))

    def always_bad(cfg):
        return "initialize outbound[1]: nope"

    with pytest.raises(ValueError, match="не помогло вычистить конфиг за 2 проходов"):
        prune_config(config, always_bad, max_passes=2)


def test_prune_config_returns_immediately_when_valid():
    config, _ = build_config(_nodes(REALITY_TCP))
    pruned, removed = prune_config(config, lambda cfg: None)
    assert pruned is config
    assert removed == []


# --- ping / выбор самой быстрой ноды ----------------------------------------


def test_select_fastest_orders_by_ping_and_caps_top():
    nodes = _nodes(REALITY_TCP, WS_TLS, GRPC_REALTITY)
    results = {
        "n0": PingResult("n0", 300.0),
        "n1": PingResult("n1", 50.0),
        "n2": PingResult("n2", 120.0),
    }
    alive, dead = select_fastest(nodes, results, top=2)
    assert [n.tag for n in alive] == ["n1", "n2"]
    assert dead == []


def test_select_fastest_drops_unreachable_nodes():
    nodes = _nodes(REALITY_TCP, WS_TLS)
    results = {
        "n0": PingResult("n0", error="ConnectionRefusedError: refused"),
        "n1": PingResult("n1", 80.0),
    }
    alive, dead = select_fastest(nodes, results, top=0)
    assert [n.tag for n in alive] == ["n1"]
    assert [d.tag for d in dead] == ["n0"]


def test_select_fastest_keeps_everything_when_nobody_answered():
    """Пинг - фильтр, а не приговор: чужая сеть не должна ломать запуск."""
    nodes = _nodes(REALITY_TCP, WS_TLS)
    results = {"n0": PingResult("n0", error="timeout"), "n1": PingResult("n1", error="timeout")}
    alive, dead = select_fastest(nodes, results, top=5)
    assert [n.tag for n in alive] == ["n0", "n1"]
    assert len(dead) == 2


def test_select_fastest_treats_missing_result_as_dead():
    nodes = _nodes(REALITY_TCP, WS_TLS)
    alive, dead = select_fastest(nodes, {"n0": PingResult("n0", 10.0)}, top=0)
    assert [n.tag for n in alive] == ["n0"]
    assert dead[0].tag == "n1"
    assert dead[0].error == "нет результата пинга"


def test_select_fastest_on_empty_input():
    assert select_fastest([], {}, top=3) == ([], [])


def test_ping_result_ok_follows_error():
    assert PingResult("n0", 12.0).ok is True
    assert PingResult("n0", error="boom").ok is False


def test_probe_nodes_measures_local_listener():
    """Реальный замер по локальному сокету: latency больше нуля, ошибок нет."""
    import socket
    import threading

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    port = server.getsockname()[1]
    stop = threading.Event()

    def serve():
        server.settimeout(0.5)
        while not stop.is_set():
            try:
                conn, _ = server.accept()
                conn.close()
            except OSError:
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        node = Node(tag="local", protocol="vless", name="local", server="127.0.0.1", port=port, uuid="u")
        results = probe_nodes([node], timeout=2.0, workers=1)
    finally:
        stop.set()
        thread.join(timeout=2)
        server.close()

    assert results["local"].ok, results["local"].error
    assert results["local"].latency_ms >= 0


def test_probe_nodes_reports_unreachable_port():
    import socket

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()  # порт свободен, но кто-то мог занять - главное, что не висящий

    node = Node(tag="dead", protocol="vless", name="dead", server="127.0.0.1", port=port, uuid="u")
    results = probe_nodes([node], timeout=0.5, workers=1)
    assert set(results) == {"dead"}
    assert isinstance(results["dead"].latency_ms, float)
    assert isinstance(results["dead"].error, str)


def test_probe_nodes_on_empty_list():
    assert probe_nodes([]) == {}


def test_format_ping_table_shows_fastest_first():
    nodes = _nodes(REALITY_TCP, WS_TLS)
    results = {"n0": PingResult("n0", 400.0), "n1": PingResult("n1", 45.0)}
    text = format_ping_table(nodes, results)
    assert text.index("n1") < text.index("n0")
    assert "45" in text
    # Обе ноды ответили - строки про неответивших быть не должно.
    assert "Не ответили" not in text


def test_format_ping_table_counts_dead_nodes():
    nodes = _nodes(REALITY_TCP, WS_TLS)
    results = {"n0": PingResult("n0", 400.0), "n1": PingResult("n1", error="timeout")}
    text = format_ping_table(nodes, results)
    assert "Не ответили: 1" in text
    assert "n1" not in text


def test_format_ping_table_without_alive_nodes():
    nodes = _nodes(REALITY_TCP)
    text = format_ping_table(nodes, {"n0": PingResult("n0", error="timeout")})
    assert "никто не ответил" in text


def test_nodes_report_includes_ping_columns(tmp_path):
    nodes = _nodes(REALITY_TCP, WS_TLS)
    path = tmp_path / "nodes.tsv"
    write_nodes_report(nodes, path, {"n0": PingResult("n0", 42.0)})
    text = path.read_text(encoding="utf-8")
    assert "ping_ms" in text
    assert "42" in text
    assert "нет пинга" in text


def test_nodes_report_without_pings_has_no_ping_columns(tmp_path):
    nodes = _nodes(REALITY_TCP)
    path = tmp_path / "nodes.tsv"
    write_nodes_report(nodes, path)
    text = path.read_text(encoding="utf-8")
    assert "ping_ms" not in text
    assert text.splitlines()[0].count("\t") == 7


# --- повторы скачивания подписки -------------------------------------------


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_retries_transient_reset(monkeypatch):
    """Vercel рвёт соединение на холодном старте - одна вспышка не должна
    выкидывать все ~100 нод источника."""
    calls: list[str] = []

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(request.get_header("User-agent"))
        if len(calls) <= 2:
            raise OSError(10054, "connection reset by peer")
        return _FakeResponse(b"vless://x")

    monkeypatch.setattr(subscriptions, "urlopen", fake_urlopen)
    monkeypatch.setattr(subscriptions.time, "sleep", lambda _s: None)
    assert fetch("https://example.org/sub", timeout=1) == "vless://x"
    # Сетевой сбой лечится повтором того же агента, а не перебором всех.
    assert calls[:2] == calls[2:3] * 2


def test_fetch_does_not_try_other_agents_on_network_error(monkeypatch):
    """После reset менять User-Agent бессмысленно.

    Старая реализация гоняла 3 попытки × 4 агента × 30 секунд, и мёртвый
    источник держал запуск на 6 минутах молча. Теперь на сетевой сбок уходит
    ровно RETRIES запросов.
    """
    calls: list[str] = []

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(request.get_header("User-agent"))
        raise OSError(10054, "connection reset by peer")

    monkeypatch.setattr(subscriptions, "urlopen", fake_urlopen)
    monkeypatch.setattr(subscriptions.time, "sleep", lambda _s: None)
    monkeypatch.setattr(subscriptions, "RETRIES", 3)
    with pytest.raises(SubscriptionError, match="10054"):
        fetch("https://example.org/sub", timeout=1)
    assert len(calls) == 3
    assert len(set(calls)) == 1


def test_fetch_switches_agent_on_non_subscription_response(monkeypatch):
    """А вот тут смена User-Agent оправдана: ответ пришёл, но это не подписка."""
    agents: list[str] = []

    def fake_urlopen(request, timeout=None, context=None):
        agent = request.get_header("User-agent")
        agents.append(agent)
        if agent == subscriptions.USER_AGENTS[0]:
            return _FakeResponse(b"<html>404</html>")
        return _FakeResponse(b"vless://x")

    monkeypatch.setattr(subscriptions, "urlopen", fake_urlopen)
    monkeypatch.setattr(subscriptions.time, "sleep", lambda _s: None)
    assert fetch("https://example.org/sub", timeout=1) == "vless://x"
    assert len(agents) == 2
    assert agents[0] != agents[1]


def test_fetch_gives_up_immediately_on_certificate_error(monkeypatch):
    """Сертификат не на тот хост - это не вспышка, повторы не помогут."""
    calls: list[int] = []

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(1)
        raise ssl.SSLCertVerificationError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self signed certificate"
        )

    monkeypatch.setattr(subscriptions, "urlopen", fake_urlopen)
    monkeypatch.setattr(subscriptions.time, "sleep", lambda _s: None)
    monkeypatch.setattr(subscriptions, "RETRIES", 3)
    with pytest.raises(SubscriptionError, match="CERTIFICATE_VERIFY_FAILED"):
        fetch("https://example.org/sub", timeout=1)
    assert len(calls) == 1


def test_fetch_gives_up_after_retries(monkeypatch):
    calls: list[int] = []

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(1)
        raise OSError("down")

    monkeypatch.setattr(subscriptions, "urlopen", fake_urlopen)
    monkeypatch.setattr(subscriptions.time, "sleep", lambda _s: None)
    monkeypatch.setattr(subscriptions, "RETRIES", 2)
    with pytest.raises(SubscriptionError, match="down"):
        fetch("https://example.org/sub", timeout=1)
    # Ровно RETRIES попыток: сетевой сбок не умножается на число агентов.
    assert len(calls) == 2


def test_fetch_skips_agent_loop_for_explicit_user_agent(monkeypatch):
    calls: list[int] = []

    def fake_urlopen(request, timeout=None, context=None):
        calls.append(1)
        return _FakeResponse(b"vless://x")

    monkeypatch.setattr(subscriptions, "urlopen", fake_urlopen)
    fetch("https://example.org/sub", timeout=1, user_agent="my-client")
    assert len(calls) == 1


# --- пайплайн выбора нод в CLI ---------------------------------------------


class _Args:
    """Минимальный Namespace для pick_fastest."""

    only = ""
    no_ping = False
    top = 10
    ping_timeout = 0.5


def test_pick_fastest_returns_single_node_without_ping():
    args = _Args()
    nodes = _nodes(REALITY_TCP, WS_TLS)
    picked, pings = pick_fastest(args, nodes[:1])
    assert [n.tag for n in picked] == ["n0"]
    assert pings == {}


def test_pick_fastest_respects_no_ping():
    args = _Args()
    args.no_ping = True
    nodes = _nodes(REALITY_TCP, WS_TLS)
    picked, pings = pick_fastest(args, nodes)
    assert len(picked) == 2
    assert pings == {}


def test_pick_fastest_respects_only(monkeypatch):
    """Явно выбранная нода пингуется впустую - проще доверить её urltest.
    Фильтр ``--only`` применяется раньше, в collect_nodes."""
    args = _Args()
    args.only = "n1"
    monkeypatch.setattr(
        "scripts.lthub_tunnel.tunnel.probe_nodes",
        lambda *a, **k: pytest.fail("--only не должен пинговать"),
    )
    nodes = _nodes(REALITY_TCP, WS_TLS)
    picked, pings = pick_fastest(args, [n for n in nodes if n.tag == "n1"])
    assert [n.tag for n in picked] == ["n1"]
    assert pings == {}


def test_pick_fastest_keeps_all_when_nobody_answers(monkeypatch):
    args = _Args()
    nodes = _nodes(REALITY_TCP, WS_TLS)
    monkeypatch.setattr(
        "scripts.lthub_tunnel.tunnel.probe_nodes",
        lambda *a, **k: {"n0": PingResult("n0", error="timeout"), "n1": PingResult("n1", error="timeout")},
    )
    picked, pings = pick_fastest(args, nodes)
    assert [n.tag for n in picked] == ["n0", "n1"]
    assert pings


def test_pick_fastest_drops_dead_and_caps(monkeypatch):
    args = _Args()
    args.top = 1
    nodes = _nodes(REALITY_TCP, WS_TLS)
    monkeypatch.setattr(
        "scripts.lthub_tunnel.tunnel.probe_nodes",
        lambda *a, **k: {"n0": PingResult("n0", 300.0), "n1": PingResult("n1", error="refused")},
    )
    picked, pings = pick_fastest(args, nodes)
    assert [n.tag for n in picked] == ["n0"]
    assert pings["n1"].error == "refused"


# --- кеш подписки -----------------------------------------------------------


def test_fetch_cached_writes_cache_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(subscriptions, "fetch", lambda url, timeout=30: "vless://fresh")
    body, cached = subscriptions.fetch_cached("https://host/sub?token=secret", cache_dir=tmp_path)
    assert (body, cached) == ("vless://fresh", False)
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    # Токен из URL в имя файла не попадает - только хост и хеш.
    assert "secret" not in files[0].name
    assert files[0].read_text(encoding="utf-8") == "vless://fresh"


def test_fetch_cached_falls_back_to_cache(monkeypatch, tmp_path):
    def boom(url, timeout=30):
        raise subscriptions.SubscriptionError("connection reset")

    monkeypatch.setattr(subscriptions, "fetch", boom)
    with pytest.raises(subscriptions.SubscriptionError):
        subscriptions.fetch_cached("https://host/sub", cache_dir=tmp_path)

    cache = subscriptions._cache_file("https://host/sub", tmp_path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("vless://stale", encoding="utf-8")
    body, cached = subscriptions.fetch_cached("https://host/sub", cache_dir=tmp_path)
    assert (body, cached) == ("vless://stale", True)


def test_fetch_cached_without_cache_dir_just_fetches(monkeypatch):
    monkeypatch.setattr(subscriptions, "fetch", lambda url, timeout=30: "vless://x")
    assert subscriptions.fetch_cached("https://host/sub") == ("vless://x", False)


def test_cache_file_name_is_stable_and_url_specific(tmp_path):
    first = subscriptions._cache_file("https://a.example/sub", tmp_path)
    again = subscriptions._cache_file("https://a.example/sub", tmp_path)
    other = subscriptions._cache_file("https://b.example/sub", tmp_path)
    assert first == again
    assert first != other
    assert first.suffix == ".txt"


def test_load_all_uses_cache_when_source_is_down(monkeypatch, tmp_path):
    url = "https://host.example/sub"
    calls: list[str] = []

    def flaky(url_arg, timeout=30):
        calls.append(url_arg)
        if len(calls) == 1:
            return REALITY_TCP
        raise subscriptions.SubscriptionError("connection reset")

    monkeypatch.setattr(subscriptions, "fetch", flaky)
    first = subscriptions.load_all([url], verbose=False, cache_dir=tmp_path)
    assert len(first) == 1
    # Второй раз источник лежит - ноды всё равно есть, из кеша.
    second = subscriptions.load_all([url], verbose=False, cache_dir=tmp_path)
    assert [n.server for n in second] == [n.server for n in first]


def test_load_all_raises_when_source_down_and_no_cache(monkeypatch, tmp_path):
    def boom(url, timeout=30):
        raise subscriptions.SubscriptionError("down")

    monkeypatch.setattr(subscriptions, "fetch", boom)
    with pytest.raises(subscriptions.SubscriptionError, match="ни одна подписка"):
        subscriptions.load_all(["https://host.example/sub"], verbose=False, cache_dir=tmp_path)


def test_node_to_clash_reality_and_ws():
    proxy = node_to_clash(parse_vless(REALITY_TCP))
    assert proxy["type"] == "vless"
    assert proxy["flow"] if "flow" in proxy else True
    assert proxy["reality-opts"]["short-id"] == "2f49bccf11150ef2"
    assert proxy["client-fingerprint"] == "chrome"
    assert proxy["servername"] == "ads.x5.ru"

    ws_proxy = node_to_clash(parse_vless(WS_TLS))
    assert ws_proxy["network"] == "ws"
    assert ws_proxy["ws-opts"]["path"] == "/ws"
    assert ws_proxy["ws-opts"]["headers"]["Host"] == "fbsv6.guardora.pro"


def test_node_to_clash_returns_none_for_unsupported():
    assert node_to_clash(parse_vless(XHTTP_NODE)) is None


def test_build_clash_groups_and_rules():
    nodes = [parse_vless(uri) for uri in (REALITY_TCP, WS_TLS, XHTTP_NODE)]
    config, rejected = build_clash(nodes)
    assert len(config["proxies"]) == 2
    assert config["proxy-groups"][0]["type"] == "url-test"
    assert config["proxy-groups"][0]["url"].endswith("generate_204")
    assert config["proxy-groups"][1]["proxies"][0] == "auto"
    assert config["rules"] == ["MATCH,auto"]
    assert len(rejected) == 1


def test_build_clash_without_usable_nodes_raises():
    with pytest.raises(ValueError, match="не осталось"):
        build_clash([parse_vless(XHTTP_NODE)])


def test_nodes_report_lists_skipped_with_reason(tmp_path):
    from scripts.lthub_tunnel.sbconfig import write_nodes_report

    nodes = [parse_vless(uri) for uri in (REALITY_TCP, XHTTP_NODE)]
    report = write_nodes_report(nodes, tmp_path / "nodes.tsv").read_text(encoding="utf-8")
    assert report.splitlines()[0].split("\t")[0] == "tag"
    assert "skip:" in report


def test_node_label_falls_back_to_server():
    assert Node(tag="n0", protocol="vless", name="", server="1.2.3.4", port=443).label == (
        "vless://1.2.3.4:443"
    )


# --- runner.py: логика окна без Tk -----------------------------------------


def _vless_uri(index: int) -> str:
    """Уникальная нода на основе заготовки REALITY_TCP.

    Готовая константа используется потому, что для reality нужен валидный
    base64 ``pbk``: с выдуманным ``pbk=k`` sing-box отвергает outbound, и тест
    проверял бы не то.
    """
    return REALITY_TCP.replace(
        "11111111-1111-1111-1111-111111111111",
        f"1111111{index}-1111-1111-1111-111111111111",
    )


def _tagged_nodes(count: int) -> list[Node]:
    """Ноды с уникальными тегами - как их делает загрузчик подписок.

    Теги проставляет ``subscriptions._with_tag``; в тестах сеть подменена, поэтому
    проставить их нужно руками, иначе все outbound получат один тег и sing-box
    откажется на duplicate tag.
    """
    return [replace(parse_vless(_vless_uri(i)), tag=f"n{i}") for i in range(count)]


def _fake_network(monkeypatch, nodes):
    """Подменить сеть: отдать готовые ноды и пинг по умолчанию «всё ответило»."""
    monkeypatch.setattr(runner, "load_all", lambda *a, **k: list(nodes))
    monkeypatch.setattr(runner, "probe_nodes", lambda *a, **k: {})
    monkeypatch.setattr(
        runner, "load_sources", lambda *a, **k: (["https://example.org"], "https://probe", 2080)
    )


def test_runner_build_collects_nodes_and_writes_config(tmp_path, monkeypatch):
    nodes = _tagged_nodes(3)
    _fake_network(monkeypatch, nodes)
    session = runner.TunnelSession(state_root=tmp_path)

    config_path = session.build()

    assert config_path.exists()
    assert session.total_count == 3
    assert session.port == 2080
    assert (tmp_path / "nodes.tsv").exists()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["outbounds"][0]["outbounds"]


def test_runner_build_falls_back_to_all_nodes_when_ping_silent(tmp_path, monkeypatch):
    """Ни одна нода не ответила - это может быть чужая сеть, а не мёртвые ноды."""
    nodes = _tagged_nodes(3)
    _fake_network(monkeypatch, nodes)
    monkeypatch.setattr(
        runner,
        "probe_nodes",
        lambda *a, **k: {n.tag: PingResult(tag=n.tag, error="таймаут") for n in nodes},
    )
    session = runner.TunnelSession(state_root=tmp_path)

    session.build()

    assert session.alive_count == 0
    # Все три ноды остались: пинг - фильтр, а не приговор.
    config = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert len(config["outbounds"][0]["outbounds"]) == 3


def test_runner_build_keeps_fastest_alive(tmp_path, monkeypatch):
    nodes = _tagged_nodes(4)
    _fake_network(monkeypatch, nodes)
    monkeypatch.setattr(
        runner,
        "probe_nodes",
        lambda *a, **k: {
            n.tag: PingResult(
                tag=n.tag,
                latency_ms=10.0 + 10 * i,
                error="" if i != 3 else "таймаут",
            )
            for i, n in enumerate(nodes)
        },
    )
    session = runner.TunnelSession(state_root=tmp_path, top=2)

    session.build()

    assert session.alive_count == 3
    config = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert len(config["outbounds"][0]["outbounds"]) == 2


def test_runner_build_reports_log(tmp_path, monkeypatch):
    nodes = _tagged_nodes(1)
    _fake_network(monkeypatch, nodes)
    lines: list[str] = []
    session = runner.TunnelSession(state_root=tmp_path, log=lines.append)

    session.build()

    assert any("Скачиваю подписки" in line for line in lines)
    assert any("Готово" in line for line in lines)


def test_runner_build_without_sources_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "load_sources", lambda *a, **k: ([], "https://probe", 2080))
    session = runner.TunnelSession(state_root=tmp_path)
    with pytest.raises(RuntimeError, match="Нет источников"):
        session.build()


def test_runner_stop_is_safe_when_not_started(tmp_path):
    session = runner.TunnelSession(state_root=tmp_path)
    assert session.running is False
    session.stop()  # не должно бросать
    assert session.running is False


def test_runner_start_requires_config(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "sing_box_path", lambda: tmp_path / "sing-box.exe")
    (tmp_path / "sing-box.exe").write_bytes(b"stub")
    session = runner.TunnelSession(state_root=tmp_path)
    session.port = 2080
    with pytest.raises(RuntimeError, match="Сначала собери конфиг"):
        session.start(settle=0)


def test_runner_install_flag_follows_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "sing_box_path", lambda: tmp_path / "sing-box.exe")
    session = runner.TunnelSession(state_root=tmp_path)
    assert session.sing_box_installed is False
    (tmp_path / "sing-box.exe").write_bytes(b"stub")
    assert session.sing_box_installed is True


def test_gui_module_imports_without_display():
    """Импорт окна не должен требовать графической среды.

    Само окно на headless-машине не откроется, а вот упасть на ``import tkinter``
    можно и в текстовом окружении - это и ловим.
    """
    import scripts.lthub_tunnel.gui as gui

    assert hasattr(gui, "TunnelApp")
    assert gui.READY == "Подключено"


# --- сборка .exe: пути внутри frozen-приложения ---------------------------


def test_frozen_bundle_dir_uses_meipass(monkeypatch):
    """В сборке ресурсы лежат во временной _MEI*, а не рядом с исходниками.

    Если искать каталог пакета обычным ``Path(__file__).parent``, приложение
    из .exe не найдёт ни sing-box, ни подписки: папка удаляется при выходе.
    """
    monkeypatch.setattr(tunnel.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tunnel.sys, "_MEIPASS", "/tmp/_MEI42", raising=False)
    assert tunnel._bundle_dir() == Path("/tmp/_MEI42")


def test_frozen_writes_beside_exe(monkeypatch, tmp_path):
    """Скачанный sing-box обязан попасть рядом с .exe, а не в _MEI*."""
    monkeypatch.setattr(tunnel.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tunnel.sys, "executable", str(tmp_path / "LthubTunnel.exe"), raising=False)
    assert tunnel.writable_bin_dir() == tmp_path / "bin"


def test_frozen_prefers_sources_next_to_exe(monkeypatch, tmp_path):
    """Пользователь может дописать подписки в файл рядом с .exe."""
    exe = tmp_path / "LthubTunnel.exe"
    exe.write_bytes(b"stub")
    beside = tmp_path / "sources.local.json"
    beside.write_text('{"urls": ["https://example.org"]}', encoding="utf-8")
    monkeypatch.setattr(tunnel.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tunnel.sys, "executable", str(exe), raising=False)

    assert tunnel.sources_file() == beside
    urls, _probe, _port = tunnel.load_sources(None)
    assert urls == ["https://example.org"]


def test_frozen_sing_box_prefers_bundled(monkeypatch, tmp_path):
    """Встроенный в сборку бинарник важнее того, что лежит рядом с .exe."""
    monkeypatch.setattr(tunnel, "BIN_DIR", tmp_path / "_MEI" / "bin")
    monkeypatch.setattr(tunnel.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tunnel.sys, "executable", str(tmp_path / "LthubTunnel.exe"), raising=False)
    (tmp_path / "_MEI" / "bin").mkdir(parents=True)
    (tmp_path / "_MEI" / "bin" / "sing-box.exe").write_bytes(b"stub")

    assert tunnel.sing_box_path() == tmp_path / "_MEI" / "bin" / "sing-box.exe"


def test_unreadable_sources_gives_actionable_error(monkeypatch, tmp_path):
    """Вместо сырого PermissionError пользователь должен видеть, что делать."""
    broken = tmp_path / "sources.local.json"
    broken.write_bytes(b"\xff\xfe not json at all")

    def boom(*_a, **_k):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_text", boom)
    with pytest.raises(RuntimeError, match="Проверь, что файл не открыт"):
        tunnel.load_sources(None)


def test_sources_fall_back_to_bundled_when_no_file(monkeypatch, tmp_path):
    """Нет файла рядом с .exe - берём подписки, зашитые в сборку.

    Так и работает первый запуск готового приложения: файла ещё нет, а
    подписки должны быть.
    """
    exe = tmp_path / "LthubTunnel.exe"
    exe.write_bytes(b"stub")
    monkeypatch.setattr(tunnel.sys, "frozen", True, raising=False)
    monkeypatch.setattr(tunnel.sys, "executable", str(exe), raising=False)
    monkeypatch.setattr(
        tunnel,
        "bundled_sources",
        lambda: {"urls": ["https://bundled.example"], "port": 2080},
    )

    urls, _probe, port = tunnel.load_sources(None)

    assert urls == ["https://bundled.example"]
    assert port == 2080