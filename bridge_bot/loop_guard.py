"""Loop guard — предотвращает циклы пересылки через метку [BOT]."""

BOT_MARK = "[BOT]"


def has_bot_mark(text: str) -> bool:
    """Check if text contains the bot mark indicating it was already forwarded.

    Args:
        text: Message text to check.

    Returns:
        True if text contains [BOT] mark, False otherwise.
    """
    return BOT_MARK in text


def add_bot_mark(text: str) -> str:
    """Add bot mark to text to prevent forwarding loops.

    Args:
        text: Original message text.

    Returns:
        Text with [BOT] mark appended.
    """
    return f"{text} {BOT_MARK}"
