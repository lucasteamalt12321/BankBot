"""Тесты разбора VPN-подписок и сборки конфигов туннеля.

Фикстуры - реальные строки из боевой подписки (агрегаторские ноды), поэтому
проверяются и грязные параметры: ``host=?TELEGRAM@...``, ``type=raw``,
отсутствующий ``fp`` у reality, ``mode=gun``.
"""

from __future__ import annotations

import base64

import pytest

from scripts.lthub_tunnel.clash import build_clash, node_to_clash
from scripts.lthub_tunnel.nodes import (
    Node,
    convert,
    parse_trojan,
    parse_vless,
    unsupported_reason,
)
from scripts.lthub_tunnel.sbconfig import build_config, prune_config
from scripts.lthub_tunnel.subscriptions import decode_body, merge, parse_subscription

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