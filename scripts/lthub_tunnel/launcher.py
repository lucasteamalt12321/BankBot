"""Точка входа для сборки .exe и для запуска окна напрямую.

Отдельный файл нужен PyInstaller: он берёт путь к скрипту, а не модуль, поэтому
пакет ``scripts.lthub_tunnel`` должен быть импортируемым отсюда.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.lthub_tunnel.gui import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
