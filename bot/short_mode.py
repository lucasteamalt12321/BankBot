"""Short response mode helpers."""

from __future__ import annotations

SHORT_MODE_KEY = "short_mode_enabled"
GLOBAL_SHORT_MODE_KEY = "global_short_mode_enabled"
DEFAULT_SHORT_MODE = True


def is_short_mode(context) -> bool:
    """Return true when concise bot replies are enabled for user or globally."""
    bot_data = getattr(context, "bot_data", {})
    user_data = getattr(context, "user_data", {})
    if SHORT_MODE_KEY in user_data:
        return bool(user_data[SHORT_MODE_KEY])
    if GLOBAL_SHORT_MODE_KEY in bot_data:
        return bool(bot_data[GLOBAL_SHORT_MODE_KEY])
    return DEFAULT_SHORT_MODE


def set_short_mode(context, enabled: bool) -> None:
    """Store personal concise response mode in PTB user_data."""
    user_data = getattr(context, "user_data", None)
    if user_data is not None:
        user_data[SHORT_MODE_KEY] = enabled


def set_global_short_mode(context, enabled: bool) -> None:
    """Store global concise response mode in PTB bot_data."""
    bot_data = getattr(context, "bot_data", None)
    if bot_data is not None:
        bot_data[GLOBAL_SHORT_MODE_KEY] = enabled


async def short_command(update, context) -> None:
    """Enable concise response mode for the current user only."""
    set_short_mode(context, True)
    await update.message.reply_text(
        "Краткий режим включён для вас. Он также используется по умолчанию.\n"
        "Команды: /start, /balance, /profile, /stats, /feedback.\n"
        "Вернуть полные ответы для себя: /long\n"
        "Включить короткий режим для всех: /short_all"
    )


async def long_command(update, context) -> None:
    """Disable concise response mode for the current user only."""
    set_short_mode(context, False)
    await update.message.reply_text(
        "Полный режим включён для вас. Вернуть короткие ответы: /short. "
        "Для всех: /long_all или /short_all."
    )


async def short_all_command(update, context) -> None:
    """Enable concise response mode globally for all users."""
    set_global_short_mode(context, True)
    await update.message.reply_text(
        "Краткий режим включён для всех. Основное:\n"
        "/balance — баланс\n"
        "/profile — профиль\n"
        "/stats — статистика\n"
        "/long — полный режим только для себя\n"
        "/long_all — полный режим для всех"
    )


async def long_all_command(update, context) -> None:
    """Disable concise response mode globally for all users."""
    set_global_short_mode(context, False)
    await update.message.reply_text(
        "Полный режим включён для всех. Личные настройки /short или /long у отдельных пользователей сохраняются."
    )
