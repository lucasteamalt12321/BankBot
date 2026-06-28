"""Family Budget bot commands for BankBot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


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
