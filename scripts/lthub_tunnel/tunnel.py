"""CLI туннеля: поднять локальный прокси sing-box и открыть сайт через него.

    python -m scripts.lthub_tunnel.tunnel install
    python -m scripts.lthub_tunnel.tunnel ping
    python -m scripts.lthub_tunnel.tunnel build
    python -m scripts.lthub_tunnel.tunnel check
    python -m scripts.lthub_tunnel.tunnel up --open
    python -m scripts.lthub_tunnel.tunnel export

Конфиг и состояние живут в ``%LOCALAPPDATA%\\lthub-tunnel`` (на других ОС -
в ``~/.local/share/lthub-tunnel``), чтобы не мусорить в репозитории.
Источники подписок читаются из ``sources.local.json`` рядом с этим файлом -
это токен доступа, в git он не попадает.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, urlopen

from scripts.lthub_tunnel.clash import build_clash, dump_clash
from scripts.lthub_tunnel.nodes import Node
from scripts.lthub_tunnel.probe import (
    DEFAULT_TIMEOUT as DEFAULT_PING_TIMEOUT,
)
from scripts.lthub_tunnel.probe import (
    DEFAULT_TOP,
    format_ping_table,
    probe_nodes,
    select_fastest,
)
from scripts.lthub_tunnel.sbconfig import (
    DEFAULT_LISTEN,
    DEFAULT_PORT,
    DEFAULT_PROBE_URL,
    build_config,
    dump_config,
    prune_config,
    write_nodes_report,
)
from scripts.lthub_tunnel.subscriptions import SubscriptionError, load_all

TOOL_DIR = Path(__file__).resolve().parent
BIN_DIR = TOOL_DIR / "bin"
SOURCES_FILE = TOOL_DIR / "sources.local.json"

DEFAULT_SITE = "https://lthub.vercel.app"
FALLBACK_VERSION = "1.14.2"
RELEASE_URL = "https://api.github.com/repos/SagerNet/sing-box/releases/latest"


def state_dir(override: str | Path | None = None) -> Path:
    """Каталог для конфига, логов и кеша sing-box."""
    if override:
        path = Path(override)
        path.mkdir(parents=True, exist_ok=True)
        return path
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    path = Path(base) / "lthub-tunnel"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sing_box_path() -> Path:
    name = "sing-box.exe" if os.name == "nt" else "sing-box"
    return BIN_DIR / name


def load_sources(explicit: list[str] | None) -> tuple[list[str], str, int]:
    """Источники подписок и пробный URL. Приоритет: CLI > sources.local.json."""
    urls = [u for u in (explicit or []) if u.strip()]
    probe_url = DEFAULT_PROBE_URL
    port = DEFAULT_PORT
    if not urls and SOURCES_FILE.exists():
        data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        urls = list(data.get("urls", []))
        probe_url = data.get("probe_url") or probe_url
        port = int(data.get("port") or port)
    return urls, probe_url, port


# --- install ---------------------------------------------------------------

def _platform_asset(version: str) -> tuple[str, bool]:
    """Имя релиза sing-box и признак, что это zip."""
    if os.name == "nt":
        return f"sing-box-{version}-windows-amd64.zip", True
    if sys.platform == "darwin":
        return f"sing-box-{version}-darwin-amd64.tar.gz", False
    return f"sing-box-{version}-linux-amd64.tar.gz", False


def _latest_version() -> str:
    try:
        request = Request(RELEASE_URL, headers={"User-Agent": "lthub-tunnel"})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read())["tag_name"].lstrip("v")
    except (URLError, OSError, ValueError, KeyError):
        return FALLBACK_VERSION


def cmd_install(args: argparse.Namespace) -> int:
    """Скачать sing-box в scripts/lthub_tunnel/bin (нужен один раз)."""
    if sing_box_path().exists() and not args.force:
        print(f"Уже установлен: {sing_box_path()}")
    else:
        version = args.version or _latest_version()
        asset, is_zip = _platform_asset(version)
        url = f"https://github.com/SagerNet/sing-box/releases/download/v{version}/{asset}"
        print(f"Качаю {version} -> {asset}")
        try:
            with urlopen(Request(url, headers={"User-Agent": "lthub-tunnel"}), timeout=300) as response:
                blob = response.read()
        except (URLError, OSError) as exc:
            print(f"Не скачалось: {exc}", file=sys.stderr)
            print("Скачай вручную и положи в", BIN_DIR, file=sys.stderr)
            return 1
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        archive = state_dir(args.state_dir) / asset
        archive.write_bytes(blob)
        _extract(archive, BIN_DIR, is_zip)
        archive.unlink(missing_ok=True)
    print(subprocess.run([str(sing_box_path()), "version"], capture_output=True, text=True).stdout.strip())
    return 0


def _extract(archive: Path, target: Path, is_zip: bool) -> None:
    """Достать исполняемый файл из архива релиза."""
    if is_zip:
        with zipfile.ZipFile(archive) as bundle:
            names = [n for n in bundle.namelist() if Path(n).name == sing_box_path().name]
            if not names:
                raise RuntimeError(f"в архиве нет {sing_box_path().name}")
            with bundle.open(names[0]) as src, (target / sing_box_path().name).open("wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(archive) as bundle:
            member = next(
                (m for m in bundle.getmembers() if Path(m.name).name == sing_box_path().name),
                None,
            )
            if member is None:
                raise RuntimeError(f"в архиве нет {sing_box_path().name}")
            member = member.replace(name=sing_box_path().name)
            with bundle.extractfile(member) as src, (target / sing_box_path().name).open("wb") as dst:
                shutil.copyfileobj(src, dst)
    binary = sing_box_path()
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


# --- build / check ---------------------------------------------------------

def collect_nodes(args: argparse.Namespace) -> tuple[list[Node], str, int]:
    """Скачать подписки и вернуть ноды, пробный URL и порт."""
    urls, probe_url, port = load_sources(args.source)
    if not urls:
        print(
            "Нет источников. Передай --source <url> или создай "
            f"{SOURCES_FILE} с ключом urls.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    try:
        nodes = load_all(
            urls,
            timeout=args.timeout,
            verbose=not args.quiet,
            # Последняя удачная подписка - запасной путь, когда источник моргает.
            cache_dir=state_dir(args.state_dir) / "subs",
        )
    except SubscriptionError as exc:
        print(f"Подписки недоступны: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if args.limit and args.limit < len(nodes):
        nodes = nodes[: args.limit]
    if args.only:
        needle = args.only.lower()
        picked = [n for n in nodes if needle in n.tag.lower() or needle in n.label.lower()]
        if not picked:
            print(f"По фильтру {args.only!r} ничего не найдено.", file=sys.stderr)
            raise SystemExit(2)
        nodes = picked
    return nodes, probe_url, port


def pick_fastest(
    args: argparse.Namespace, nodes: list[Node]
) -> tuple[list[Node], dict[str, object]]:
    """Отсечь мёртвые ноды пингом и оставить самые быстрые.

    Пинг - только фильтр: окончательный выбор делает ``urltest`` внутри
    sing-box, уже по сквозной задержке. Поэтому ``--only`` (явно выбранная
    нода) и ``--no-ping`` пинг пропускают, а если не ответил никто - конфиг
    собирается из всех нод, чтобы чужая сеть не ломала запуск.
    """
    if args.only or args.no_ping or len(nodes) <= 1:
        return nodes, {}
    print(f"Пингую {len(nodes)} нод (таймаут {args.ping_timeout:.1f} с)...")
    results = probe_nodes(nodes, timeout=args.ping_timeout)
    alive, dead = select_fastest(nodes, results, top=args.top)
    alive_count = len(nodes) - len(dead)
    if not dead:
        print(f"  ответили все {alive_count}")
        return alive, results
    if not alive_count:
        print(f"  не ответил никто - пинг пропущен, беру все {len(nodes)}")
        return nodes, results
    print(f"  живых {alive_count} из {len(nodes)}, мёртвых {len(dead)}, в конфиг беру {len(alive)}")
    for result in dead[:5]:
        print(f"  - {result.tag}: {result.error[:90]}")
    if len(dead) > 5:
        print(f"  - ... ещё {len(dead) - 5}")
    return alive, results


def sing_box_check(config_path: Path) -> str | None:
    """Прогнать ``sing-box check``. None - конфиг валиден, иначе текст ошибки."""
    if not sing_box_path().exists():
        return "sing-box не установлен, выполни: python -m scripts.lthub_tunnel.tunnel install"
    result = subprocess.run(
        [str(sing_box_path()), "check", "-c", str(config_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0:
        return None
    message = (result.stderr or result.stdout or "").strip()
    # sing-box печатает ANSI-цвета - для парсинга они лишние.
    return re.sub(r"\x1b\[[0-9;]*m", "", message)


def cmd_build(args: argparse.Namespace) -> int:
    """Собрать config.json и показать статистику по нодам."""
    nodes, probe_url, port = collect_nodes(args)
    nodes, pings = pick_fastest(args, nodes)
    home = state_dir(args.state_dir)
    config, rejected = build_config(
        nodes,
        port=port,
        probe_url=probe_url,
        cache_file=home / "cache.db",
        log_level=args.log_level,
    )
    config_path = home / "config.json"
    dump_config(config, config_path)
    # Пока sing-box ругается на конкретный outbound - выкидываем его.
    try:
        config, pruned = prune_config(config, lambda cfg: sing_box_check(_dump_tmp(cfg, config_path)))
    except ValueError as exc:
        print(f"Конфиг не собрался: {exc}", file=sys.stderr)
        return 1
    dump_config(config, config_path)
    report = write_nodes_report(nodes, home / "nodes.tsv", pings or None)

    usable = len(config["outbounds"][0]["outbounds"])
    print(f"Нод разобрано: {len(nodes)}, в urltest: {usable}, отброшено: {len(rejected)}")
    for node, reason in rejected[:10]:
        print(f"  - {node.label}: {reason}")
    if len(rejected) > 10:
        print(f"  ... ещё {len(rejected) - 10}")
    for line in pruned[:10]:
        print(f"  * выкинул {line}")
    if len(pruned) > 10:
        print(f"  * ... ещё {len(pruned) - 10}")
    _report_best(nodes, pings, config["outbounds"][0].get("outbounds", []))
    print(f"Конфиг:  {config_path}")
    print(f"Отчёт:   {report}")
    print(f"Проба:   {probe_url}")
    return 0


def _report_best(nodes: list[Node], pings: dict, kept_tags: list[str]) -> None:
    """Сказать, какая нода быстрее всего ответила на пинг."""
    if not pings:
        return
    by_tag = {node.tag: node for node in nodes}
    ranked = sorted((r for r in pings.values() if r.ok), key=lambda r: r.latency_ms)
    best = next((r for r in ranked if r.tag in kept_tags), None)
    if best is None:
        print("Ни одна нода не ответила на пинг - выбор сделает urltest.")
        return
    print(f"Быстрее всего ответила {by_tag[best.tag].label} ({best.latency_ms:.0f} мс)")
    print(f"  Окончательный выбор делает urltest по сквозной задержке ({len(kept_tags)} нод в группе).")


def _dump_tmp(config: dict, config_path: Path) -> Path:
    """Положить конфиг на диск - sing-box check умеет только файлы."""
    dump_config(config, config_path)
    return config_path


def cmd_check(args: argparse.Namespace) -> int:
    """Собрать конфиг и показать вердикт sing-box."""
    if cmd_build(args):
        return 1
    error = sing_box_check(state_dir(args.state_dir) / "config.json")
    print("sing-box check:", "ок" if error is None else f"ошибка\n{error}")
    return 0 if error is None else 1


# --- up --------------------------------------------------------------------

def wait_port(host: str, port: int, timeout: float = 30.0) -> bool:
    """Дождаться, пока прокси начнёт слушать порт."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.3)
    return False


def probe(url: str, proxy_port: int, timeout: int = 25, attempts: int = 8, delay: float = 5.0) -> tuple[bool, str]:
    """Открыть URL через прокси с ретраями. Возвращает (ок, описание).

    Первые попытки нужны потому, что urltest ещё не закончил замер нод и
    группа может временно вести на мёртвую. Следующий цикл urltest (минута)
    уводит группу на живую ноду - поэтому повторяем заметно дольше.
    """
    proxy = f"http://{DEFAULT_LISTEN}:{proxy_port}"
    opener = urllib.request.build_opener(ProxyHandler({"http": proxy, "https": proxy}))
    last = "неизвестная ошибка"
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        try:
            with opener.open(url, timeout=timeout) as response:
                elapsed = (time.monotonic() - started) * 1000
                return response.status < 400, f"HTTP {response.status} за {elapsed:.0f} мс"
        except (URLError, OSError, ValueError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < attempts:
            time.sleep(delay)
    return False, f"после {attempts} попыток - {last}"


def find_browser() -> Path | None:
    """Первый найденный браузер Chromium для запуска с прокси."""
    relative = (
        ("Microsoft/Edge/Application/msedge.exe",)
        if os.name == "nt"
        else ("google-chrome", "chromium", "chromium-browser")
    )
    if os.name != "nt":
        for name in relative:
            found = shutil.which(name)
            if found:
                return Path(found)
        return None
    roots = [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")),
    ]
    for root in roots:
        if not root:
            continue
        candidate = root / relative[0]
        if candidate.exists():
            return candidate
    return None


def open_site(url: str, proxy_port: int, state_root: Path) -> None:
    """Открыть сайт в отдельном профиле браузера, который ходит через прокси."""
    browser = find_browser()
    if browser is None:
        print(f"Браузер не найден. Открой вручную: {url}")
        print(f"Прокси: http://{DEFAULT_LISTEN}:{proxy_port}")
        return
    profile = state_root / "browser-profile"
    subprocess.Popen(
        [
            str(browser),
            f"--proxy-server=http://{DEFAULT_LISTEN}:{proxy_port}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--new-window",
            url,
        ]
    )
    print(f"Открываю {url} через прокси {DEFAULT_LISTEN}:{proxy_port}")


def cmd_up(args: argparse.Namespace) -> int:
    """Поднять прокси, проверить сайт и (по --open) открыть браузер."""
    if not sing_box_path().exists():
        print("Сначала: python -m scripts.lthub_tunnel.tunnel install", file=sys.stderr)
        return 1
    if cmd_build(args):
        return 1

    home = state_dir(args.state_dir)
    config_path = home / "config.json"
    _, _, port = load_sources(None)
    log_path = home / "sing-box.log"
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [str(sing_box_path()), "run", "-c", str(config_path), "-D", str(home)],
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    try:
        if not wait_port(DEFAULT_LISTEN, port, timeout=40):
            print("Прокси не поднялся, лог:", file=sys.stderr)
            print(log_path.read_text(encoding="utf-8", errors="replace")[-2000:], file=sys.stderr)
            return 1
        print(f"Прокси слушает {DEFAULT_LISTEN}:{port} (лог: {log_path})")
        if args.settle:
            print(f"Даю urltest {args.settle} с на замер нод...")
            time.sleep(args.settle)
        ok, detail = probe(args.site, port)
        print(f"{args.site} -> {'ДОСТУПЕН' if ok else 'НЕДОСТУПЕН'} ({detail})")
        if not ok:
            print("Что делать:", file=sys.stderr)
            print(f"  1. перезапустить: {Path(sys.argv[0]).name} up --open", file=sys.stderr)
            print("  2. конкретную ноду: --only n7 (список в nodes.tsv)", file=sys.stderr)
            print(f"  3. лог sing-box: {log_path}", file=sys.stderr)
            tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
            for line in tail:
                print("     " + line, file=sys.stderr)
        if args.open:
            open_site(args.site, port, home)
            print("Ctrl+C - закрыть туннель и завершить работу.")
            try:
                process.wait()
            except KeyboardInterrupt:
                pass
        else:
            input("Enter - закрыть туннель. ")
        return 0 if ok else 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        log_file.close()


# --- export ----------------------------------------------------------------

def cmd_export(args: argparse.Namespace) -> int:
    """Выгрузить конфиги для раздачи пользователям (sing-box + Clash).

    Пинг обязателен: раздавать телефон десятки заведомо мёртвых нод бессмысленно,
    клиент всё равно не отличит их друг от друга. В конфиг попадают только
    живые и самые быстрые - их на телефоне уже не так много.
    """
    nodes, probe_url, port = collect_nodes(args)
    nodes, pings = pick_fastest(args, nodes)
    out = Path(args.out)
    home = state_dir(args.state_dir)
    sb_config, sb_rejected = build_config(
        nodes, port=port, probe_url=probe_url, cache_file=home / "cache.db"
    )
    config_path = out / ".sing-box-check.json"
    dump_config(sb_config, config_path)
    try:
        sb_config, pruned = prune_config(
            sb_config, lambda cfg: sing_box_check(_dump_tmp(cfg, config_path))
        )
    except ValueError as exc:
        config_path.unlink(missing_ok=True)
        print(f"Конфиг не собрался: {exc}", file=sys.stderr)
        return 1
    config_path.unlink(missing_ok=True)

    dump_config(sb_config, out / "lthub-sing-box.json")
    clash_config, clash_rejected = build_clash(nodes, probe_url=probe_url)
    dump_clash(clash_config, out / "lthub-clash.yaml")
    write_nodes_report(nodes, out / "lthub-nodes.tsv", pings or None)
    _report_best(nodes, pings, sb_config["outbounds"][0].get("outbounds", []))
    for line in pruned[:5]:
        print(f"  * выкинул {line}")
    print(f"sing-box: {out / 'lthub-sing-box.json'} (отброшено {len(sb_rejected)})")
    print(f"Clash:    {out / 'lthub-clash.yaml'} (отброшено {len(clash_rejected)})")
    print(f"Ноды TSV: {out / 'lthub-nodes.tsv'}")
    return 0


def cmd_ping(args: argparse.Namespace) -> int:
    """Показать, кто отвечает и с какой задержкой - без сборки конфига."""
    nodes, _, _ = collect_nodes(args)
    if args.limit and args.limit < len(nodes):
        nodes = nodes[: args.limit]
    print(f"Пингую {len(nodes)} нод (таймаут {args.ping_timeout:.1f} с)...")
    results = probe_nodes(nodes, timeout=args.ping_timeout)
    alive, _dead = select_fastest(nodes, results, top=args.top)
    print(format_ping_table(alive, results, limit=args.limit or 0))
    if alive:
        by_tag = {node.tag: node for node in nodes}
        best = min(alive, key=lambda node: results[node.tag].latency_ms)
        print(f"Лучшая по пингу: {by_tag[best.tag].label} ({results[best.tag].latency_ms:.0f} мс)")
        print("Это TCP/TLS-пинг. Сквозную задержку меряет urltest при запуске прокси.")
    else:
        print("Ни одна нода не ответила.", file=sys.stderr)
        return 1
    return 0


# --- cli -------------------------------------------------------------------

def _common_options() -> argparse.ArgumentParser:
    """Опции, общие для всех подкоманд.

    Вынесены в подпарсеры, а не в корневой: иначе пришлось бы писать
    ``--state-dir`` до имени команды, что непривычно.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--site", default=DEFAULT_SITE, help="какой сайт проверяем")
    parser.add_argument(
        "--state-dir",
        default="",
        help="где хранить config.json/логи (по умолчанию %%LOCALAPPDATA%%\\lthub-tunnel)",
    )
    parser.add_argument("--source", action="append", help="URL подписки (можно дважды)")
    parser.add_argument("--timeout", type=int, default=30, help="таймаут скачивания подписки")
    parser.add_argument("--limit", type=int, default=0, help="взять только N нод")
    parser.add_argument(
        "--only",
        default="",
        help="оставить одну ноду (тег n7 или часть имени) - для отладки конкретной",
    )
    parser.add_argument(
        "--ping-timeout",
        type=float,
        default=DEFAULT_PING_TIMEOUT,
        help="таймаут пинга одной ноды в секундах",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help=f"сколько самых быстрых нод оставить в конфиге (0 - всех живых, по умолчанию {DEFAULT_TOP})",
    )
    parser.add_argument(
        "--no-ping",
        action="store_true",
        help="не пинговать, собрать конфиг из всех нод",
    )
    parser.add_argument(
        "--log-level",
        default="warn",
        choices=["trace", "debug", "info", "warn", "error"],
    )
    parser.add_argument("--quiet", action="store_true", help="не печатать статистику источников")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lthub-tunnel", description=__doc__.splitlines()[0])
    common = _common_options()
    sub = parser.add_subparsers(dest="command", required=True)

    install = sub.add_parser("install", parents=[common], help="скачать sing-box")
    install.add_argument("--version", default="", help="версия sing-box (по умолчанию latest)")
    install.add_argument("--force", action="store_true")
    install.set_defaults(func=cmd_install)

    sub.add_parser("ping", parents=[common], help="замерить пинг всех нод").set_defaults(func=cmd_ping)
    sub.add_parser("build", parents=[common], help="собрать config.json").set_defaults(func=cmd_build)
    sub.add_parser("check", parents=[common], help="собрать и проверить конфиг").set_defaults(
        func=cmd_check
    )

    up = sub.add_parser("up", parents=[common], help="поднять прокси и проверить сайт")
    up.add_argument("--open", action="store_true", help="открыть сайт в браузере")
    up.add_argument(
        "--settle",
        type=int,
        default=12,
        help="сколько секунд ждать первый замер urltest (0 - не ждать)",
    )
    up.set_defaults(func=cmd_up)

    export = sub.add_parser("export", parents=[common], help="выгрузить конфиги для пользователей")
    export.add_argument("--out", default=str(TOOL_DIR / "dist"), help="каталог для выгрузки")
    export.set_defaults(func=cmd_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())