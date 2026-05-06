"""Canonical templates and aliases for the parameteric template coder.

The coder intentionally does not store pair/triple/four-template phrase tables.
All phrase semantics are derived from the mutable dialogue state in
``bot.template_coder.service``.
"""

from __future__ import annotations

TEMPLATES: dict[int, str] = {
    1: "ОК",
    2: "Да",
    3: "Спасибо",
    4: '"Спасибо, нет"',
    5: "Великолепно",
    6: "Спасибо еще раз",
    7: "Скоро увидимся",
    8: "Скоро буду",
    9: "Я занят(а)",
    10: "Нет",
}

ALIASES: dict[str, int] = {
    "ок": 1,
    "okay": 1,
    "ok": 1,
    "да": 2,
    "спасибо": 3,
    "спасибо нет": 4,
    "спасибо, нет": 4,
    '"спасибо, нет"': 4,
    "нет спасибо": 4,
    "нет, спасибо": 4,
    "великолепно": 5,
    "спасибо еще раз": 6,
    "спасибо ещё раз": 6,
    "скоро увидимся": 7,
    "скоро буду": 8,
    "я занят": 9,
    "я занята": 9,
    "я занят(а)": 9,
    "занят": 9,
    "занята": 9,
    "нет": 10,
}

ARRIVAL_CODE = 8
BUSY_CODE = 9
GOODBYE_CODE = 7
THANKS_CODE = 3
REPEAT_THANKS_CODE = 6
POLITE_REFUSAL_CODE = 4
AGREEMENT_CODE = 2
NEGATION_CODE = 10
OK_CODE = 1
ENTHUSIASM_CODE = 5
