"""Family Budget bot commands for BankBot."""

import re

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.budget_parser import parse_expense_line, resolve_member

AWAIT_EXPENSES = 1


async def budget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /budget — открывает Family Budget веб-приложение."""
    if not update.message:
        return

    user_id = update.effective_user.id
    base_url = context.bot_data.get("budget_base_url", "https://bank-bot-ruby.vercel.app")
    app_url = f"{base_url}/family_budget?user_id={user_id}"

    keyboard = [[InlineKeyboardButton("💰 Открыть семейный бюджет", url=app_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "💰 Семейный бюджет\n\n"
        "Ведите учёт семейных трат, автоматически рассчитывайте долги\n"
        "и погашайте их частями.\n\n"
        "📖 Что внутри:\n"
        "• Создайте семью или присоединитесь по коду\n"
        "• Добавляйте траты — долги создаются автоматически\n"
        "• Смотрите, кто кому должен\n"
        "• Погашайте долги с пересчётом\n\n"
        "Нажмите кнопку ниже, чтобы открыть в браузере:",
        reply_markup=reply_markup,
    )


async def family_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /family — управление семьёй."""
    if not update.message:
        return

    args = context.args or []
    if not args:
        await update.message.reply_text(
            "📋 Управление семьёй\n\n"
            "Доступные команды:\n"
            "• /family create <название> — создать новую семью\n"
            "• /family join <код> — присоединиться к семье\n"
            "• /family info — информация о вашей семье\n"
            "• /family leave — выйти из семьи\n"
            "• /budget — открыть веб-приложение"
        )
        return

    subcommand = args[0].lower()

    if subcommand == "create":
        if len(args) < 2:
            await update.message.reply_text("Укажите название семьи: /family create <название>")
            return
        name = " ".join(args[1:]).strip()
        await _create_family(update, name)
    elif subcommand == "join":
        if len(args) < 2:
            await update.message.reply_text("Укажите код приглашения: /family join <код>")
            return
        code = args[1].strip()
        await _join_family(update, code)
    elif subcommand == "info":
        await _family_info(update, context)
    elif subcommand == "leave":
        await _leave_family(update, context)
    else:
        await update.message.reply_text(f"Неизвестная подкоманда: {subcommand}")


async def _create_family(update: Update, name: str):
    """Create a family via API."""
    import httpx

    user_id = update.effective_user.id
    display_name = update.effective_user.first_name or f"User{user_id}"
    base_url = "https://bank-bot-ruby.vercel.app"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                f"{base_url}/api/budget/family/create",
                json={"name": name, "display_name": display_name},
                headers={"X-User-Id": str(user_id)},
            )
            data = res.json()
            if res.status_code == 201 and "family" in data:
                code = data["family"]["invite_code"]
                await update.message.reply_text(
                    f"✅ Семья «{name}» создана!\n\n"
                    f"📌 Код приглашения: <code>{code}</code>\n\n"
                    f"Поделитесь этим кодом с членами семьи, чтобы они могли присоединиться "
                    f"через /family join <код>",
                    parse_mode="HTML",
                )
            else:
                await update.message.reply_text(f"❌ Ошибка: {data.get('error', 'неизвестная ошибка')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось создать семью: {e}")


async def _join_family(update: Update, code: str):
    """Join a family via API."""
    import httpx

    user_id = update.effective_user.id
    display_name = update.effective_user.first_name or f"User{user_id}"
    base_url = "https://bank-bot-ruby.vercel.app"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                f"{base_url}/api/budget/family/join",
                json={"code": code, "display_name": display_name},
                headers={"X-User-Id": str(user_id)},
            )
            data = res.json()
            if "family" in data:
                await update.message.reply_text(
                    f"✅ Вы присоединились к семье «{data['family']['name']}»!\n\n"
                    f"Откройте /budget чтобы начать учёт трат."
                )
            else:
                await update.message.reply_text(f"❌ Ошибка: {data.get('error', 'неверный код')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось присоединиться: {e}")


async def _family_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show family info."""
    import httpx

    user_id = update.effective_user.id
    base_url = "https://bank-bot-ruby.vercel.app"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"{base_url}/api/budget/family/status?user_id={user_id}",
                headers={"X-User-Id": str(user_id)},
            )
            data = res.json()
            if not data.get("family"):
                await update.message.reply_text("❌ Вы не состоите ни в одной семье.")
                return

            f = data["family"]
            members_text = "\n".join(
                f"• {m['display_name']} {'(админ)' if m['user_id'] == f['admin_id'] else ''}"
                for m in f.get("members", [])
            )
            await update.message.reply_text(
                f"🏠 Семья: {f['name']}\n"
                f"📌 Код: <code>{f['invite_code']}</code>\n\n"
                f"👥 Участники ({len(f.get('members', []))}):\n{members_text}",
                parse_mode="HTML",
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


async def _leave_family(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leave a family (if not admin)."""
    import httpx

    user_id = update.effective_user.id
    base_url = "https://bank-bot-ruby.vercel.app"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"{base_url}/api/budget/family/status?user_id={user_id}",
                headers={"X-User-Id": str(user_id)},
            )
            data = res.json()
            if not data.get("family"):
                await update.message.reply_text("❌ Вы не состоите ни в одной семье.")
                return

            if data["family"]["admin_id"] == str(user_id):
                await update.message.reply_text(
                    "❌ Вы администратор семьи. Передайте права или расформируйте семью "
                    "через веб-приложение."
                )
                return

            # Since we don't have a leave endpoint yet, redirect to web app
            app_url = f"{base_url}/family_budget?user_id={user_id}"
            keyboard = [[InlineKeyboardButton("💰 Открыть семейный бюджет", url=app_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Выход из семьи пока доступен только через веб-приложение.",
                reply_markup=reply_markup,
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


# ─── AI Expense Entry ─────────────────────────────────────────────────


async def _call_api_create_transaction(
    context: ContextTypes.DEFAULT_TYPE, family_id: int, txn_data: dict
) -> dict | None:
    """Call POST /api/budget/transactions to create a single expense."""
    base_url = context.bot_data.get(
        "budget_base_url", "https://bank-bot-ruby.vercel.app"
    )
    payload = {
        "family_id": family_id,
        "payer_id": txn_data["payer_id"],
        "for_whom_ids": txn_data["for_whom_ids"],
        "amount": txn_data["amount"],
        "category": txn_data["category"],
        "description": txn_data["description"],
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                f"{base_url}/api/budget/transactions",
                json=payload,
                headers={"X-User-Id": str(txn_data["payer_id"])},
            )
            if res.status_code == 201:
                return res.json()
            return None
    except Exception:
        return None


async def _fetch_family_info(user_id: str, base_url: str) -> dict | None:
    """Get family info for a user via API."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(
                f"{base_url}/api/budget/family/status?user_id={user_id}",
                headers={"X-User-Id": str(user_id)},
            )
            data = res.json()
            return data.get("family")
    except Exception:
        return None


async def add_expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: /addexpense – start AI-driven expense entry."""
    user_id = str(update.effective_user.id)
    base_url = context.bot_data.get(
        "budget_base_url", "https://bank-bot-ruby.vercel.app"
    )

    family = await _fetch_family_info(user_id, base_url)
    if not family:
        await update.message.reply_text(
            "❌ Вы не состоите в семье.\n"
            "Сначала создайте её: /family create <название>\n"
            "или присоединитесь: /family join <код>"
        )
        return ConversationHandler.END

    context.user_data["budget_family_id"] = family["id"]
    context.user_data["budget_members"] = family.get("members", [])

    names = "\n".join(f"• {m['display_name']}" for m in family["members"])

    await update.message.reply_text(
        "📝 Отправьте список трат построчно.\n\n"
        "Формат каждой строки:\n"
        "<code>Кредитор Должник Сумма [Категория] [Комментарий]</code>\n\n"
        "Примеры:\n"
        "<code>Лука Мама 500 еда за пиццу</code>\n"
        "<code>Юля Лука 1000 Другое за шахматы</code>\n\n"
        f"Участники семьи:\n{names}\n\n"
        "Отправьте /cancel чтобы отменить.",
        parse_mode="HTML",
    )
    return AWAIT_EXPENSES


async def add_expense_handle_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Process the expense lines sent by the user."""
    text = update.message.text.strip()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    family_id = context.user_data.get("budget_family_id")
    members = context.user_data.get("budget_members", [])

    if not family_id or not members:
        await update.message.reply_text(
            "❌ Сессия устарела. Начните заново: /addexpense"
        )
        return ConversationHandler.END

    parsed = []
    errors = []
    for i, line in enumerate(lines, 1):
        txn = parse_expense_line(line, members)
        if txn:
            parsed.append(txn)
        else:
            errors.append(f"Строка {i}: <code>{line}</code> — не удалось распознать")

    if not parsed:
        await update.message.reply_text(
            "❌ Не удалось распознать ни одной траты.\n"
            + ("\n".join(errors) + "\n\n" if errors else "")
            + "Попробуйте ещё раз или /cancel"
        )
        return AWAIT_EXPENSES

    success = 0
    fail = 0
    result_lines = []
    for txn in parsed:
        res = await _call_api_create_transaction(context, family_id, txn)
        if res:
            success += 1
            line_text = f"✅ {txn['amount']}₽ — {txn['category']}"
            if txn["description"]:
                line_text += f" ({txn['description']})"
            result_lines.append(line_text)
        else:
            fail += 1
            result_lines.append(f"❌ {txn['amount']}₽ — ошибка сервера")

    report = "\n".join(result_lines)
    if errors:
        report += "\n\n⚠️ Не удалось распознать:\n" + "\n".join(errors)

    report += f"\n\n✅ Создано: {success}, ❌ Ошибок: {fail}"
    await update.message.reply_text(report)

    context.user_data.clear()
    return ConversationHandler.END


async def add_expense_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel the conversation."""
    context.user_data.clear()
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


def get_budget_handlers():
    """Return handlers for Budget AI expense entry."""
    return [
        ConversationHandler(
            entry_points=[CommandHandler("addexpense", add_expense_start)],
            states={
                AWAIT_EXPENSES: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, add_expense_handle_text
                    )
                ],
            },
            fallbacks=[CommandHandler("cancel", add_expense_cancel)],
            per_user=True,
            per_chat=True,
        ),
    ]
