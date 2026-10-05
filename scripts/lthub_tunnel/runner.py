"""Логика туннеля без интерфейса: собрать конфиг, поднять и снять прокси.

Отдельный модуль потому, что у туннеля два лица - консоль (``tunnel.py``) и
окно (``gui.py``). Всё, что нельзя проверить кликом мыши, живёт здесь и
тестируется обычными тестами; ``gui.py`` только рисует кнопки и перекладывает
события в этот класс.

    session = TunnelSession(log=print)
    session.build()          # подписки -> пинг -> config.json
    session.start()          # sing-box + ожидание порта
    session.check_site()     # (True, 'HTTP 200 за 828 мс')
    session.stop()
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from pathlib import Path

from scripts.lthub_tunnel.nodes import Node
from scripts.lthub_tunnel.probe import (
    DEFAULT_TIMEOUT as DEFAULT_PING_TIMEOUT,
)
from scripts.lthub_tunnel.probe import (
    DEFAULT_TOP,
    probe_nodes,
    select_fastest,
)
from scripts.lthub_tunnel.sbconfig import DEFAULT_LISTEN, build_config, dump_config, prune_config
from scripts.lthub_tunnel.subscriptions import load_all
from scripts.lthub_tunnel.tunnel import (
    DEFAULT_SITE,
    _dump_tmp,
    install_sing_box,
    load_sources,
    open_site,
    probe,
    sing_box_check,
    sing_box_path,
    state_dir,
    wait_port,
    write_nodes_report,
)

LogFn = Callable[[str], None]


def _noop(_message: str) -> None:
    """Заглушка лога, чтобы класс не зависел от вывода."""


class TunnelSession:
    """Состояние одного туннеля: конфиг, процесс sing-box, сайт для проверки."""

    def __init__(
        self,
        state_root: str | Path | None = None,
        sources: list[str] | None = None,
        site: str = DEFAULT_SITE,
        top: int = DEFAULT_TOP,
        ping_timeout: float = DEFAULT_PING_TIMEOUT,
        log: LogFn = _noop,
    ) -> None:
        self.home = state_dir(state_root)
        self.sources = sources
        self.site = site
        self.top = top
        self.ping_timeout = ping_timeout
        self.log = log
        self.config_path = self.home / "config.json"
        self.process: subprocess.Popen | None = None
        self._log_file = None
        self.nodes: list[Node] = []
        self.best_label = ""
        self.alive_count = 0
        self.total_count = 0
        self.port = 0

    # --- состояние ---------------------------------------------------------

    @property
    def running(self) -> bool:
        """Жив ли процесс sing-box."""
        return self.process is not None and self.process.poll() is None

    @property
    def sing_box_installed(self) -> bool:
        return sing_box_path().exists()

    def install(self) -> None:
        """Скачать sing-box, если его ещё нет."""
        install_sing_box(log=self.log)

    # --- сборка ------------------------------------------------------------

    def build(self) -> Path:
        """Скачать подписки, отобрать лучшие ноды и собрать валидный конфиг.

        Порядок ровно как в CLI, и по той же причине: пинг - фильтр, а
        окончательный выбор делает ``urltest`` внутри sing-box уже по сквозной
        задержке.
        """
        urls, probe_url, port = load_sources(self.sources)
        if not urls:
            raise RuntimeError(
                "Нет источников подписок: создай sources.local.json или передай --source"
            )
        self.port = port
        self.log("Скачиваю подписки...")
        nodes = load_all(urls, timeout=15, cache_dir=self.home / "subs")
        self.total_count = len(nodes)
        self.log(f"Нод в подписках: {len(nodes)}")

        results = probe_nodes(nodes, timeout=self.ping_timeout) if len(nodes) > 1 else {}
        if results:
            alive, dead = select_fastest(nodes, results, top=self.top)
            self.alive_count = len(nodes) - len(dead)
            if self.alive_count:
                self.log(f"Живых {self.alive_count} из {len(nodes)}, в конфиг беру {len(alive)}")
                nodes = alive
            else:
                # Ни одна нода не ответила - это может быть чужая сеть, а не
                # мёртвые ноды. Собираем из всех: urltest разберётся сам.
                self.log(f"Не ответил никто - пинг пропущен, беру все {len(nodes)}")
        else:
            self.alive_count = len(nodes)

        self.nodes = nodes
        self.best_label = self._best_label(nodes, results)
        config, _rejected = build_config(
            nodes, port=port, probe_url=probe_url, cache_file=self.home / "cache.db"
        )
        dump_config(config, self.config_path)
        self.log("Проверяю конфиг sing-box...")
        try:
            config, pruned = prune_config(
                config, lambda cfg: sing_box_check(_dump_tmp(cfg, self.config_path))
            )
        except ValueError as exc:
            raise RuntimeError(f"Конфиг не собрался: {exc}") from exc
        dump_config(config, self.config_path)
        for line in pruned[:3]:
            self.log(f"выкинул битую ноду: {line}")
        write_nodes_report(nodes, self.home / "nodes.tsv")
        if self.best_label:
            self.log(f"Лучшая нода: {self.best_label}")
        self.log(f"Готово. Прокси {DEFAULT_LISTEN}:{port}")
        return self.config_path

    def _best_label(self, nodes: list[Node], results: dict) -> str:
        """Нода с наименьшей задержкой среди тех, что попали в конфиг.

        Это лучший результат нашего пинга, а не победитель ``urltest``: тот
        определится только после запуска прокси, когда появится сквозная задержка.
        """
        kept = {node.tag for node in nodes}
        alive = [r for r in results.values() if r.ok and r.tag in kept]
        if not alive:
            return ""
        best = min(alive, key=lambda r: r.latency_ms)
        node = next((n for n in nodes if n.tag == best.tag), None)
        return f"{best.latency_ms:.0f} мс — {node.label if node else best.tag}"

    # --- процесс -----------------------------------------------------------

    def start(self, settle: float = 12.0) -> None:
        """Запустить sing-box и дождаться, пока прокси начнёт слушать порт."""
        if self.running:
            return
        if not self.sing_box_installed:
            raise RuntimeError("sing-box не установлен")
        if not self.config_path.exists():
            raise RuntimeError("Сначала собери конфиг")
        log_path = self.home / "sing-box.log"
        self._log_file = log_path.open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [str(sing_box_path()), "run", "-c", str(self.config_path), "-D", str(self.home)],
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
        )
        if not wait_port(DEFAULT_LISTEN, self.port, timeout=40):
            self.stop()
            raise RuntimeError("Прокси не поднялся, смотри лог sing-box.log")
        self.log(f"Прокси слушает {DEFAULT_LISTEN}:{self.port}")
        if settle > 0:
            self.log(f"Даю urltest {settle:.0f} с на замер нод...")
            time.sleep(settle)

    def check_site(self, attempts: int = 4) -> tuple[bool, str]:
        """Открыть ли сайт через прокси."""
        return probe(self.site, self.port, attempts=attempts, timeout=20, delay=2.0)

    def browse(self) -> None:
        """Открыть сайт в браузере, направленном через прокси."""
        if not self.running:
            raise RuntimeError("Туннель не поднят")
        open_site(self.site, self.port, self.home)

    def stop(self) -> None:
        """Остановить sing-box. Безопасно вызывать, если он не запущен."""
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
