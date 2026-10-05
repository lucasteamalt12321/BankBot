"""Собрать один .exe с окном туннеля. Windows, без внешних зависимостей на выходе.

    python scripts\\lthub_tunnel\\build_exe.py

На выходе ``dist/LthubTunnel.exe``: двойной клик - и открылось окно. Внутри
код приложения, tkinter и сам sing-box, поэтому подписки и бинарник на машине
пользователя больше не нужны.

PyInstaller ставится отдельно: ``pip install pyinstaller``. Если его нет или сборка
не удалась, скрипт честно об этом говорит и оставляет рабочий вариант
``python -m scripts.lthub_tunnel.gui``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOL_DIR.parent.parent
APP_NAME = "LthubTunnel"


def have_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        return False
    return True


BUNDLED_MODULE = TOOL_DIR / "_bundled.py"


def generate_bundled_sources() -> bool:
    """Зашить sources.local.json в модуль, чтобы он попал внутрь .exe.

    Именно модулем, а не файлом: PyInstaller кладёт данные во временную папку
    ``_MEI*``, содержимое которой на заражённых антивирусом машинах читать
    нельзя - приложение падало с ``PermissionError`` на первом же запуске.
    """
    sources = TOOL_DIR / "sources.local.json"
    if not sources.exists():
        BUNDLED_MODULE.unlink(missing_ok=True)
        return False
    payload = json.dumps(json.loads(sources.read_text(encoding="utf-8")), ensure_ascii=False)
    BUNDLED_MODULE.write_text(
        '"""Сгенерировано build_exe.py. Подписки, зашитые в .exe."""\n\n'
        f"PAYLOAD = {payload!r}\n",
        encoding="utf-8",
    )
    return True


def main() -> int:
    if sys.platform != "win32":
        print("Сборка .exe рассчитана на Windows; на других ОС запускай python -m scripts.lthub_tunnel.gui")
        return 1
    if not have_pyinstaller():
        print("Нужен PyInstaller: pip install pyinstaller", file=sys.stderr)
        return 1
    if not generate_bundled_sources():
        print("Внимание: sources.local.json не найден - приложение откроется без подписок.")

    binary = TOOL_DIR / "bin" / "sing-box.exe"
    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", APP_NAME,
        # Точка входа - тонкий скрипт: так пакет scripts не нужно добавлять
        # в hiddenimports руками и меньше шанс собрать мусор.
        str(TOOL_DIR / "launcher.py"),
        "--paths", str(REPO_ROOT),
        "--distpath", str(TOOL_DIR / "dist"),
        "--workpath", str(TOOL_DIR / "build"),
        "--specpath", str(TOOL_DIR / "build"),
    ]
    if binary.exists():
        # Кладём sing-box внутрь .exe: без него на чужой машине нечего запускать.
        command += ["--add-data", f"{binary}{';'}bin"]
    else:
        print("Внимание: sing-box.exe не найден, он не попадёт внутрь сборки.")

    print("Запускаю:", " ".join(command[:6]), "...")
    result = subprocess.run(command, cwd=REPO_ROOT)
    if result.returncode != 0:
        print("Сборка не удалась", file=sys.stderr)
        return result.returncode

    exe = TOOL_DIR / "dist" / f"{APP_NAME}.exe"
    if not exe.exists():
        print(f"Ожидался {exe}, но его нет", file=sys.stderr)
        return 1
    exe.chmod(exe.stat().st_mode | 0o111)
    size = exe.stat().st_size / (1024 * 1024)
    print(f"Готово: {exe} ({size:.1f} МБ)")
    return 0


def cleanup() -> None:
    """Убрать сборочные каталоги (build/, spec) - они в .gitignore."""
    for name in ("build",):
        shutil.rmtree(TOOL_DIR / name, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
