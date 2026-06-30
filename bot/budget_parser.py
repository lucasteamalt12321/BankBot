"""Parser for Family Budget expense lines — no PTB dependency."""

from __future__ import annotations

import re

KNOWN_CATEGORIES = {"еда", "транспорт", "хозяйство", "развлечения", "другое"}


def resolve_member(name: str, members: list[dict]) -> str | None:
    """Find member user_id by display name (case-insensitive)."""
    name_lower = name.lower().strip()
    for m in members:
        if m["display_name"].lower() == name_lower:
            return m["user_id"]
    for m in members:
        if name_lower in m["display_name"].lower():
            return m["user_id"]
    return None


def parse_expense_line(line: str, members: list[dict]) -> dict | None:
    """Parse 'Creditor Debtor Amount [Category] [Comment]'.

    Returns dict with payer_id, for_whom_ids, amount, category, description
    or None if the line can not be parsed.
    """
    line = line.strip()
    if not line:
        return None

    m = re.search(r"(\d+)\s*", line)
    if not m:
        return None

    amount = int(m.group(1))
    if amount <= 0:
        return None

    before = line[: m.start()].strip()
    after = line[m.end() :].strip()

    parts = before.split(maxsplit=1)
    if len(parts) < 2:
        return None

    creditor_name, debtor_name = parts[0], parts[1]

    creditor_id = resolve_member(creditor_name, members)
    debtor_id = resolve_member(debtor_name, members)
    if not creditor_id or not debtor_id:
        return None

    category = "Другое"
    description = ""
    if after:
        after_parts = after.split(maxsplit=1)
        first_word = after_parts[0]
        if first_word.lower() in KNOWN_CATEGORIES:
            category = first_word.capitalize()
            if len(after_parts) > 1:
                description = after_parts[1]
        else:
            description = after

    return {
        "payer_id": creditor_id,
        "for_whom_ids": [debtor_id],
        "amount": amount,
        "category": category,
        "description": description,
    }
