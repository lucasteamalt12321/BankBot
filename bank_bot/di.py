"""DI-контейнер — re-export из core/di.py."""

from core.di import DIContainer, get_container, reset_container

__all__ = ["DIContainer", "get_container", "reset_container"]
