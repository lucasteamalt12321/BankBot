"""D&D команды для Telegram бота."""

import logging
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes

from core.systems.dnd_system import DndSystem

if TYPE_CHECKING:
    from bot.bot import BankBot

logger = logging.getLogger(__name__)


def register_dnd_commands(bot: "BankBot") -> None:
    """Регистрация D&D команд."""
    bot.application.add_handlers(
        [
            bot.application.add_handler(bot.conv_handler),
        ]
    )


async def dnd_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /dnd - информация о D&D системе."""
    text = """
🎲 <b>D&D Мастерская</b>

Система для проведения настольных ролевых игр в Telegram.

📋 <b>Доступные команды:</b>

1. <b>Создание сессии:</b>
   /dnd_create <название> [описание] - создать новую сессию

2. <b>Присоединение к сессии:</b>
   /dnd_join <id_сессии> - присоединиться к сессии
   /dnd_sessions - ваши D&D сессии

3. <b>Бросок кубиков:</b>
   /dnd_roll <тип> [модификатор] [цель] - бросок кубиков
   Пример: /dnd_roll d20+5 "Атака мечом"

🎯 <b>Доступные кубики:</b>
   d4, d6, d8, d10, d12, d20, d100

💡 <b>Советы:</b>
   • Мастер создает сессию и приглашает игроков
   • Используйте бросок кубиков для определения успеха действий
   • Расширенные персонажи и квесты будут подключены отдельным обновлением
     """
    await update.message.reply_text(text, parse_mode="HTML")


async def dnd_create_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, get_db
) -> None:
    """Команда /dnd_create - создание D&D сессии."""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "❌ Используйте: /dnd_create <название> [описание]\n"
            'Пример: /dnd_create "Поход в подземелье" "Исследование древних руин"'
        )
        return

    name = context.args[0]
    description = " ".join(context.args[1:]) if len(context.args) > 1 else None

    db = next(get_db())
    try:
        dnd = DndSystem(db)
        session = dnd.create_session(user.id, name, description)

        text = f"""
🎲 <b>D&D сессия создана!</b>

Название: {name}
{"Описание: " + description if description else ""}
ID сессии: {session.id}
Мастер: {user.first_name}
Максимум игроков: {session.max_players}

👥 Игроки могут присоединиться:
/dnd_join {session.id}
        """

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in dnd_create command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def dnd_join_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, get_db
) -> None:
    """Команда /dnd_join - присоединение к D&D сессии."""
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("❌ Используйте: /dnd_join <id_сессии>")
        return

    session_id = int(context.args[0])

    db = next(get_db())
    try:
        dnd = DndSystem(db)
        success = dnd.join_session(session_id, user.id)

        if success:
            session_info = dnd.get_session_info(session_id)
            if session_info:
                text = f"""
✅ <b>Вы присоединились к D&D сессии!</b>

Название: {session_info["name"]}
ID сессии: {session_info["id"]}
Мастер: Пользователь #{session_info["master_id"]}
Игроков: {session_info["current_players"]}/{session_info["max_players"]}

💡 Сессия появится в /dnd_sessions у мастера. Расширенные персонажи будут подключены отдельным обновлением.
                    """

                await update.message.reply_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(
                "❌ Не удалось присоединиться к сессии. Возможные причины:\n"
                "• Сессия уже началась\n"
                "• Достигнут лимит игроков\n"
                "• Вы уже участвуете в сессии\n"
                "• Сессия не найдена"
            )
    except Exception as e:
        logger.error(f"Error in dnd_join command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def dnd_sessions_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, get_db
) -> None:
    """Команда /dnd_sessions - список D&D сессий."""
    user = update.effective_user

    db = next(get_db())
    try:
        dnd = DndSystem(db)
        sessions = dnd.get_player_sessions(user.id)

        if not sessions:
            await update.message.reply_text("📭 Вы не участвуете ни в одной D&D сессии")
            return

        text = "🎲 <b>Ваши D&D сессии</b>\n\n"

        for session in sessions:
            status_icon = {
                "planning": "📋",
                "active": "🎮",
                "completed": "✅",
            }.get(session["status"], "❓")

            text += f"{status_icon} <b>{session['name']}</b>\n"
            text += f"   ID: {session['id']}\n"
            text += f"   Статус: {session['status']}\n"
            text += f"   Вы: {'Мастер' if session['is_master'] else 'Игрок'}\n"
            text += f"   Создана: {session['created_at'].strftime('%d.%m.%Y')}\n\n"

        text += "💡 Присоединиться к сессии: /dnd_join <id>"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in dnd_sessions command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def dnd_roll_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, get_db
) -> None:
    """Команда /dnd_roll - бросок кубиков."""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "❌ Используйте: /dnd_roll <тип_кубика> [модификатор] [цель]\n"
            "Примеры:\n"
            "/dnd_roll d20\n"
            "/dnd_roll d20+5\n"
            '/dnd_roll 2d6+3 "Урон мечом"\n'
            '/dnd_roll d100 "Шанс удачи"'
        )
        return

    dice_input = context.args[0]
    purpose = " ".join(context.args[1:]) if len(context.args) > 1 else None

    try:
        if "d" not in dice_input:
            raise ValueError("Неверный формат кубика")

        dice_input = dice_input.replace(" ", "")

        if dice_input[0].isdigit():
            dice_count_str = ""
            i = 0
            while i < len(dice_input) and dice_input[i].isdigit():
                dice_count_str += dice_input[i]
                i += 1
            dice_count = int(dice_count_str)
            dice_type = dice_input[i:]
        else:
            dice_count = 1
            dice_type = dice_input

        modifier = 0
        if "+" in dice_type:
            dice_type, modifier_str = dice_type.split("+")
            modifier = int(modifier_str)
        elif "-" in dice_type:
            dice_type, modifier_str = dice_type.split("-")
            modifier = -int(modifier_str)

        valid_dice = ["d4", "d6", "d8", "d10", "d12", "d20", "d100"]
        if dice_type not in valid_dice:
            raise ValueError(f"Неверный тип кубика. Доступные: {', '.join(valid_dice)}")

        if dice_count < 1 or dice_count > 100:
            raise ValueError("Количество кубиков должно быть от 1 до 100")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка парсинга: {str(e)}")
        return

    db = next(get_db())
    try:
        dnd = DndSystem(db)
        sessions = dnd.get_player_sessions(user.id)
        active_session = next((s for s in sessions if s["status"] == "active"), None)
        session_id = active_session["id"] if active_session else None

        if session_id:
            dice_roll = dnd.roll_dice(
                user.id,
                session_id,
                dice_type,
                dice_count,
                modifier,
                purpose=purpose,
            )
            if not dice_roll:
                await update.message.reply_text("❌ Не удалось сохранить бросок кубиков.")
                return
            result = dice_roll.result
            total = dice_roll.total
            results_text = str(result)
        else:
            results = dnd.roll_preview(dice_type, dice_count)
            result = sum(results)
            total = result + modifier
            results_text = ", ".join(map(str, results))

        text = f"""
🎲 <b>Бросок кубиков</b>

Игрок: {user.first_name}
Кубики: {dice_count}{dice_type}
{"Модификатор: " + ("+" if modifier >= 0 else "") + str(modifier) if modifier != 0 else ""}
{"Цель: " + purpose if purpose else ""}
{"Сессия: #" + str(session_id) if session_id else "Сессия: не выбрана, бросок не сохранён"}

📊 <b>Результаты:</b>
   • Выпавшие значения: {results_text}
   • Сумма: {result}
   • {"С модификатором: " + str(total) if modifier != 0 else ""}

🎯 <b>Итог:</b> {total}
        """

        await update.message.reply_text(text, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error in dnd_roll command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()
