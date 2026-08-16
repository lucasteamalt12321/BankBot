"""Модуль «Императоры России» — данные и хелперы.

Лёгкий stdlib-пакет (только dataclasses, как `core/canon`): без внешних
зависимостей, чтобы api/index.py (Vercel) импортировал его напрямую.
"""

from core.history.emperors import (
    EMPERORS,
    EVENTS,
    PERSONS,
    RULERS,
    Emperor,
    HistoryEvent,
    Person,
    emperor_by_id,
    events_for_emperor,
    persons_for_emperor,
)

__all__ = [
    "EMPERORS",
    "EVENTS",
    "PERSONS",
    "RULERS",
    "Emperor",
    "HistoryEvent",
    "Person",
    "emperor_by_id",
    "events_for_emperor",
    "persons_for_emperor",
]
