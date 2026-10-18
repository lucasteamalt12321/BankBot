"""BUG-06: границы на количество кубиков в одном броске.

Без верхней границы `999999999d6` заставлял синхронный цикл
`random.randint` крутиться ~миллиард раз прямо в event loop Telegram-бота.
"""

import pytest

from bot.handlers.dnd_message_handler import MAX_DICE_COUNT, classify_message, parse_dice


def test_parse_dice_normal():
    assert parse_dice("2d6") == {"count": 2, "sides": 6, "modifier": 0}
    assert parse_dice("3к8+2") == {"count": 3, "sides": 8, "modifier": 2}
    assert parse_dice("1d20-1") == {"count": 1, "sides": 20, "modifier": -1}


def test_parse_dice_defaults_to_single_die():
    assert parse_dice("d20") == {"count": 1, "sides": 20, "modifier": 0}


def test_parse_dice_rejects_unbounded_count():
    assert parse_dice("999999999d6") is None
    assert parse_dice(f"{MAX_DICE_COUNT + 1}d6") is None


def test_parse_dice_allows_boundary_and_rejects_zero():
    assert parse_dice(f"{MAX_DICE_COUNT}d6") is not None
    assert parse_dice("0d6") is None


def test_parse_dice_rejects_unknown_sides():
    assert parse_dice("5d7") is None


def test_classify_still_recognises_dice_text():
    # Классификатор по-прежнему видит «кубиковый» текст; решение о том,
    # исполнять ли его, принимает parse_dice (и откатывается к d20-превью).
    assert classify_message("999999999d6") == "dice"
    assert parse_dice("999999999d6") is None
