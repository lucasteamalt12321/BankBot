"""Перечень канонических произведений (Блок 3.2 канона)."""

from __future__ import annotations

from core.canon import CanonWork

# Уровни: high (🔵), medium (🟡), low (🔴), archive (архив).
CANON_WORKS: tuple[CanonWork, ...] = (
    # ── Треки (высокий канон, 🔵) ────────────────────────────────────────
    CanonWork(
        title="Рома",
        kind="track",
        author="Олег",
        date="11.12.2025",
        canon_level="high",
        url="https://t.me/lucasteamgroup/17764",
    ),
    CanonWork(
        title="Олег, как ты задолбал",
        kind="track",
        author="LucasTeam",
        date="26.12.2025",
        canon_level="high",
        url="https://t.me/lucasteamgroup/23796",
    ),
    CanonWork(
        title="Дисс на Антона",
        kind="track",
        author="LucasTeam",
        date="",
        canon_level="high",
        url="",
    ),
    CanonWork(
        title="Олеговирус",
        kind="track",
        author="Рома",
        date="",
        canon_level="high",
        url="",
    ),
    CanonWork(
        title="Олег пришёл назад (legacy)",
        kind="track",
        author="LucasTeam",
        date="",
        canon_level="high",
        url="",
    ),
    CanonWork(
        title="Тень агента (V.2)",
        kind="track",
        author="Рома",
        date="24.04.2026",
        canon_level="high",
        url="https://t.me/lucasteamgroup/29990",
    ),
    CanonWork(
        title="Конфетный рай (Sugar Crash)",
        kind="track",
        author="LucasTeam",
        date="29.04.2026",
        canon_level="high",
        url="https://t.me/lucasteamgroup/30102",
    ),
    CanonWork(
        title="Восемь километров (походный дневник)",
        kind="track",
        author="LucasTeam",
        date="03.05.2026",
        canon_level="high",
        url="https://t.me/lucasteamgd/703",
    ),
    # ── Треки (средний канон, 🟡) ────────────────────────────────────────
    CanonWork(
        title="Лука",
        kind="track",
        author="Олег",
        date="",
        canon_level="medium",
        url="",
    ),
    # ── Треки (неканон, 🔴) ──────────────────────────────────────────────
    CanonWork(
        title="Вирус LucasTeamLuke",
        kind="track",
        author="Олег",
        date="",
        canon_level="low",
        url="",
    ),
    # ── Статьи (высокий канон, 🔵) ───────────────────────────────────────
    CanonWork(
        title="Чайная религия (Teaology)",
        kind="article",
        author="LucasTeam",
        date="27.04.2026",
        canon_level="high",
        url="https://t.me/lucasteamgroup/30105",
    ),
    CanonWork(
        title="Философия конфет: девять кругов сладкого искупления",
        kind="article",
        author="LucasTeam",
        date="02.05.2026",
        canon_level="high",
        url="https://t.me/lucasteamgd/705",
    ),
    CanonWork(
        title="Рейтинг участников чата по системе LTRS™",
        kind="article",
        author="LucasTeam",
        date="06.05.2026",
        canon_level="high",
        url="https://t.me/lucasteamgroup/30306",
    ),
    # ── Статьи (средний канон, 🟡) ───────────────────────────────────────
    CanonWork(
        title="Olegovirus checkmarevus",
        kind="article",
        author="LucasTeam",
        date="",
        canon_level="medium",
        url="",
    ),
    # ── Статьи (неканон, 🔴) ─────────────────────────────────────────────
    CanonWork(
        title="LukasTeamLuke sp. nov.",
        kind="article",
        author="O&G Research Group (Олег)",
        date="",
        canon_level="low",
        url="",
    ),
    # ── Архивные материалы (не являются частью канона) ──────────────────
    CanonWork(
        title="Пивология (Zythology)",
        kind="archive",
        author="Роман Хрущёв",
        date="12.05.2026",
        canon_level="archive",
        url="https://t.me/lucasteamgroup/30435",
    ),
)


def works_by_level(level: str) -> list[CanonWork]:
    """Произведения заданного уровня канонизации."""
    return [work for work in CANON_WORKS if work.canon_level == level]


def works_by_kind(kind: str) -> list[CanonWork]:
    """Произведения заданного типа (track/article/archive)."""
    return [work for work in CANON_WORKS if work.kind == kind]
