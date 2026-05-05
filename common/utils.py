"""Общие утилиты для всех ботов проекта."""

from __future__ import annotations


def truncate(text: str, max_len: int = 200) -> str:
    """Обрезает строку до max_len символов с многоточием.

    Args:
        text: Исходная строка.
        max_len: Максимальная длина результата.

    Returns:
        Обрезанная строка.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
