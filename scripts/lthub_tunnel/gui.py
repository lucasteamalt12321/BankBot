"""Окно туннеля: кнопка «Подключить», статус и лог. Без этого файл не нужен.

Запуск:

    python -m scripts.lthub_tunnel.gui

Собрать один .exe (Windows):

    python scripts\\lthub_tunnel\\build_exe.py

Вся логика - в ``runner.TunnelSession``, здесь только виджеты. Долгие операции
(скачивание подписок, пинг, запуск sing-box) идут в отдельном потоке, иначе окно
белеет на десятки секунд; результат возвращается в очередь и разбирается в
главном потоке через ``after``.
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import scrolledtext

from scripts.lthub_tunnel.runner import TunnelSession
from scripts.lthub_tunnel.sbconfig import DEFAULT_LISTEN
from scripts.lthub_tunnel.tunnel import DEFAULT_SITE

IDLE = "Отключено"
CONNECTING = "Подключение..."
READY = "Подключено"

BG_IDLE = "#2b2b2b"
BG_READY = "#1f4d2b"
BG_BUSY = "#4d3b1f"
FG = "#f0f0f0"


class TunnelApp:
    """Окно приложения. Поток с логикой один, UI читает очередь сообщений."""

    def __init__(self, root: tk.Tk, state_root: str | None = None) -> None:
        self.root = root
        self.queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False
        self.pending = ""
        self.session = TunnelSession(
            state_root=state_root, site=DEFAULT_SITE, log=self._log
        )
        root.title("Туннель lthub")
        root.configure(bg=BG_IDLE)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_widgets()
        self.root.after(100, self._drain)
        self._log(f"Прокси: {DEFAULT_LISTEN}:{self.session.port or 2080}")
        self._log(f"Сайт для проверки: {DEFAULT_SITE}")
        if not self.session.sing_box_installed:
            self._set_status("Нужен sing-box", "Нажми «Подключить» — скачаю автоматически")

    # --- интерфейс ---------------------------------------------------------

    def _build_widgets(self) -> None:
        pad = {"padx": 14, "pady": 6}
        self.status = tk.Label(
            self.root, text=IDLE, font=("Segoe UI", 15, "bold"),
            bg=BG_IDLE, fg=FG, **pad,
        )
        self.status.pack(fill="x")

        self.detail = tk.Label(
            self.root, text="", font=("Segoe UI", 9), bg=BG_IDLE, fg="#b0b0b0",
            wraplength=430, justify="center", **pad,
        )
        self.detail.pack(fill="x")

        self.button = tk.Button(
            self.root, text="Подключить", command=self._toggle,
            font=("Segoe UI", 12), width=20, height=1, cursor="hand2",
        )
        self.button.pack(pady=10)

        buttons = tk.Frame(self.root, bg=BG_IDLE)
        buttons.pack()
        tk.Button(
            buttons, text="Открыть сайт", command=self._browse,
            font=("Segoe UI", 9), width=16, cursor="hand2",
        ).pack(side="left", padx=4)
        tk.Button(
            buttons, text="Выход", command=self._on_close,
            font=("Segoe UI", 9), width=10, cursor="hand2",
        ).pack(side="left", padx=4)

        self.log_box = scrolledtext.ScrolledText(
            self.root, height=11, width=58, font=("Consolas", 8),
            bg="#1e1e1e", fg="#d0d0d0", insertbackground=FG, state="disabled",
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(4, 10))

    def _log(self, message: str) -> None:
        """Лог из рабочего потока: сначала в очередь, рисуется в главном."""
        self.queue.put(("log", message))

    def _set_status(self, text: str, detail: str = "", bg: str = BG_IDLE) -> None:
        self.queue.put(("status", (text, detail, bg)))

    # --- рабочий поток -----------------------------------------------------

    def _work(self, target: Callable[[], object]) -> None:
        """Выполнить долгую операцию, не блокируя окно."""

        def runner() -> None:
            try:
                target()
            except Exception as exc:  # noqa: BLE001 - окно должно показать любую ошибку
                self.queue.put(("error", str(exc)))
            finally:
                # Поток обязан сам доложить о конце: иначе после ошибки кнопка
                # осталась бы заблокированной навсегда.
                self.queue.put(("done", None))

        threading.Thread(target=runner, daemon=True).start()

    def _toggle(self) -> None:
        if self.busy:
            return
        if self.session.running:
            self.busy, self.pending = True, "Отключение..."
            self._set_status("Отключение...", bg=BG_BUSY)
            target = self._disconnect
        else:
            self.busy, self.pending = True, "Подключение..."
            self._set_status(CONNECTING, "Скачиваю подписки и меряю задержку нод", BG_BUSY)
            target = self._connect
        self._refresh_button()
        self._work(target)

    def _connect(self) -> None:
        if not self.session.sing_box_installed:
            self._set_status("Устанавливаю sing-box...", bg=BG_BUSY)
            self.session.install()
        self.session.build()
        self._set_status("Поднимаю прокси...", bg=BG_BUSY)
        self.session.start()
        ok, detail = self.session.check_site()
        if ok:
            self._set_status(READY, detail, BG_READY)
            self._log(f"Сайт доступен: {detail}")
        else:
            # Прокси поднят, но сайт не открылся - это не повод его ронять.
            self._set_status("Подключено, сайт не открылся", detail, BG_BUSY)
            self._log(f"Сайт не открылся: {detail}")
            self._log("Ноды из списка могли умереть - попробуй «Подключить» ещё раз.")

    def _disconnect(self) -> None:
        self.session.stop()
        self._set_status(IDLE, "", BG_IDLE)
        self._log("Отключено")

    def _browse(self) -> None:
        if not self.session.running:
            self._set_status(IDLE, "Сначала подключись")
            return
        try:
            self.session.browse()
        except Exception as exc:  # noqa: BLE001
            self._log(f"Не открылся браузер: {exc}")

    # --- очередь сообщений -------------------------------------------------

    def _drain(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._append(str(payload))
                elif kind == "status":
                    text, detail, bg = payload  # type: ignore[misc]
                    self._render_status(text, str(detail), str(bg))
                elif kind == "error":
                    self._render_status("Ошибка", str(payload), "#5c1f1f")
                    self._append(f"Ошибка: {payload}")
                elif kind == "done":
                    # Поток закончил: только теперь кнопку можно отпустить.
                    # Раньше она разблокировалась по таймеру, и второй клик
                    # успевал запустить ещё один sing-box на занятый порт.
                    self.busy = False
                    self.pending = ""
                    self._refresh_button()
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _refresh_button(self) -> None:
        """Пока поток занят - кнопка заблокирована, иначе смотрит на прокси."""
        if self.busy:
            self.button.config(state="disabled", text=self.pending)
        else:
            self.button.config(
                state="normal",
                text="Отключить" if self.session.running else "Подключить",
            )

    def _render_status(self, text: str, detail: str, bg: str) -> None:
        self.status.config(text=text, bg=bg)
        self.detail.config(text=detail, bg=bg)
        self.root.configure(bg=bg)

    def _append(self, message: str) -> None:
        self.log_box.config(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def _on_close(self) -> None:
        self.session.stop()
        self.root.destroy()


def selftest(log_path: str) -> int:
    """Прогнать путь подключения без окна и записать результат в файл.

    Нужно для проверки именно собранного ``.exe``: там по-другому находятся
    подписки и sing-box, и ошибка видна только внутри бинарника. Окно в этом
    режиме не создаётся, поэтому работает и без кликов.
    """
    lines: list[str] = []
    session = TunnelSession(log=lines.append)
    code = 1
    try:
        if not session.sing_box_installed:
            session.install()
        session.build()
        session.start(settle=8)
        ok, detail = session.check_site(attempts=2)
        lines.append(f"САЙТ: {'ДОСТУПЕН' if ok else 'НЕДОСТУПЕН'} ({detail})")
        code = 0 if ok else 1
    except Exception as exc:  # noqa: BLE001 - сюда пишем всё, что пошло не так
        lines.append(f"ОШИБКА: {type(exc).__name__}: {exc}")
        code = 1
    finally:
        session.stop()
    Path(log_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return code


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--selftest" in sys.argv[1:]:
        target = args[0] if args else str(Path.home() / "lthub-selftest.log")
        return selftest(target)
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"Не удалось открыть окно: {exc}", file=sys.stderr)
        return 1
    TunnelApp(root, state_root=args[0] if args else None)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
