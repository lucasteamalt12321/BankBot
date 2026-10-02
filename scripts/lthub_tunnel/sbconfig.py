"""Сборка конфига sing-box из подписки.

Схема простая и специально локальная:

* inbound ``mixed`` на ``127.0.0.1:<port>`` - один порт и HTTP, и SOCKS5,
  поэтому достаточно передать его браузеру как ``--proxy-server``;
* outbound-группа ``urltest`` - sing-box сам меряет задержку до каждой ноды
  и переключается на живую. Проба идёт **по нашему же health-эндпоинту**,
  так что в группу попадают только ноды, из которых открывается сайт;
* ``route.final = auto`` - весь трафик локального прокси идёт в туннель.

Драйвер/TUN не используются: права администратора не нужны.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from pathlib import Path

from scripts.lthub_tunnel.nodes import Node, convert, unsupported_reason

DEFAULT_LISTEN = "127.0.0.1"
DEFAULT_PORT = 2080
# Проба намеренно лёгкая (204 без тела): Vercel-рукендстарт даёт секунды задержки
# и из-за этого urltest меряет холодный старт, а не скорость туннеля.
# Сайт проверяется отдельно, через прокси, с ретраями.
DEFAULT_PROBE_URL = "https://cp.cloudflare.com/generate_204"
# Минута, а не пять: ноды из бесплатных подписок постоянно умирают, и группа
# должна уметь уйти на живую, не дожидаясь следующего длинного цикла.
DEFAULT_PROBE_INTERVAL = "1m"
# Сколько раз подряд выкидываем ноду, на которую ругается sing-box check.
MAX_PRUNE_PASSES = 15
# sing-box пишет индекс по-разному: "outbound[22]: ..." при инициализации и
# "outbounds[6].transport: ..." при разборе схемы - ловим оба.
_OUTBOUND_ERROR_RE = re.compile(r"outbounds?\[(\d+)\]")
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Убрать цветовые коды - sing-box красит лог даже в не-TTY."""
    return _ANSI_RE.sub("", text)


def build_config(
    nodes: Sequence[Node],
    *,
    listen: str = DEFAULT_LISTEN,
    port: int = DEFAULT_PORT,
    probe_url: str = DEFAULT_PROBE_URL,
    probe_interval: str = DEFAULT_PROBE_INTERVAL,
    cache_file: str | Path | None = None,
    log_level: str = "warn",
) -> tuple[dict, list[tuple[Node, str]]]:
    """Вернуть (конфиг sing-box, список отброшенных нод с причинами)."""
    outbounds: list[dict] = []
    rejected: list[tuple[Node, str]] = []
    for node in nodes:
        outbound, reason = convert(node)
        if outbound is None:
            rejected.append((node, reason or unsupported_reason(node) or "неизвестная причина"))
            continue
        outbounds.append(outbound)

    if not outbounds:
        raise ValueError("после фильтрации не осталось ни одной рабочей ноды")

    config: dict = {
        "log": {"level": log_level, "timestamp": True},
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": listen,
                "listen_port": port,
            }
        ],
        "outbounds": [
            {
                "type": "urltest",
                "tag": "auto",
                "outbounds": [outbound["tag"] for outbound in outbounds],
                "url": probe_url,
                "interval": probe_interval,
                "tolerance": 100,
                "idle_timeout": "30m",
                # Не рвём текущие соединения при смене ноды: иначе посреди
                # загрузки страницы или проигрывания трека соединение обрывается.
                "interrupt_exist_connections": False,
            },
            *outbounds,
            {"type": "direct", "tag": "direct"},
        ],
        "route": {"final": "auto"},
    }
    if cache_file:
        config["experimental"] = {
            "cache_file": {"enabled": True, "path": str(cache_file)}
        }
    return config, rejected


def prune_config(
    config: dict,
    check: Callable[[dict], str | None],
    max_passes: int = MAX_PRUNE_PASSES,
) -> tuple[dict, list[str]]:
    """Выкидывать ноды, на которые ругается sing-box, пока конфиг не пройдёт.

    Подписки бесплатные и в них регулярно попадаются ноды с полями, которых
    нет в sing-box (экзотический ``flow``, незнакомый транспорт). Без этого
    одна такая нода рушит весь конфиг и не поднимается туннель вообще.
    ``check`` получает конфиг и возвращает текст ошибки либо ``None``.
    Индекс в ошибке - позиция во всём массиве ``outbounds``, где 0 занимает
    сама группа urltest.
    """
    removed: list[str] = []
    for _ in range(max_passes):
        error = check(config)
        if not error:
            return config, removed
        error = strip_ansi(error)
        match = _OUTBOUND_ERROR_RE.search(error)
        if not match:
            raise ValueError(f"sing-box check не понимает ошибку: {error.strip()}")
        index = int(match.group(1))
        if index == 0 or index >= len(config["outbounds"]):
            # Индекс 0 - это сама группа urltest, её ругаться не на что.
            raise ValueError(f"sing-box check: {error.strip()}")
        dropped = config["outbounds"].pop(index)
        tag = dropped.get("tag", f"#{index}")
        removed.append(f"{tag}: {error.strip()}")
        group = config["outbounds"][0]
        if tag in group.get("outbounds", []):
            group["outbounds"].remove(tag)
    if check(config):
        raise ValueError(f"не помогло вычистить конфиг за {max_passes} проходов")
    return config, removed


def dump_config(config: dict, path: str | Path) -> Path:
    """Записать конфиг в UTF-8 без BOM и вернуть путь."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def write_nodes_report(nodes: Sequence[Node], path: str | Path) -> Path:
    """Выгрузить разобранные ноды в TSV - чтобы глазами видеть, что нашлось."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["tag\tprotocol\tserver\tport\tnetwork\tsecurity\tsni\tname"]
    for node in nodes:
        reason = unsupported_reason(node)
        lines.append(
            "\t".join(
                [
                    node.tag,
                    node.protocol,
                    node.server,
                    str(node.port),
                    node.network,
                    "skip:" + reason if reason else node.security,
                    node.sni,
                    node.label,
                ]
            )
        )
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target