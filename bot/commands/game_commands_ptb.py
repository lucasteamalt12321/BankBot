"""Game commands for python-telegram-bot."""

from telegram import Update
from telegram.ext import ContextTypes

from database.database import get_db
from core.systems.games_system import GamesSystem
from bot.short_mode import is_short_mode


GAME_TYPE_LABELS = {
    "cities": "Города",
    "killer_words": "Слова, которые могут убить",
    "gd_levels": "Уровни Geometry Dash",
}


async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /games - информация о мини-играх"""
    if is_short_mode(context):
        await update.message.reply_text(
            "Мини-игры:\n"
            "/play cities — города\n"
            "/play killer_words — слова\n"
            "/play gd_levels — GD уровни\n"
            "/join <id>, /startgame <id>, /turn <ход>"
        )
        return

    text = """
🎮 <b>Мини-игры</b>

Доступные игры:

1. <b>🏙 Города</b>
   • Классическая игра в города
   • Назовите город на последнюю букву предыдущего
   • Награда: 5 монет за ход
   • Команды: /play cities

2. <b>🔪 Слова, которые могут убить</b>
   • Придумывайте "убийственные" слова
   • Слова связанные с оружием, ядами и т.д.
   • Награда: до 15 монет за слово
   • Команды: /play killer_words

3. <b>🎵 Уровни GD</b>
   • Аналог игры в города, но с уровнями Geometry Dash
   • Награда: 5 монет за ход
   • Команды: /play gd_levels

📝 <b>Как играть:</b>
1. Создайте игру: /play <тип_игры>
2. Другие игроки присоединяются: /join <id_игры>
3. Начинайте игру: /startgame <id_игры>
4. Делайте ходы: /turn <ваш_ход>

🎯 <b>Текущие активные игры:</b>
   /games_list — список активных игр
     """
    await update.message.reply_text(text, parse_mode="HTML")


async def games_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /games_list - список активных мини-игр."""
    db = next(get_db())
    try:
        games = GamesSystem(db)
        sessions = games.get_active_sessions()
        if not sessions:
            await update.message.reply_text(
                "🎮 Активных мини-игр сейчас нет.\n"
                "Создайте игру: /play cities, /play killer_words или /play gd_levels"
            )
            return

        lines = ["🎮 <b>Активные мини-игры</b>"]
        for session in sessions:
            game_label = GAME_TYPE_LABELS.get(session["game_type"], session["game_type"])
            status = "ожидание" if session["status"] == "waiting" else "идёт"
            lines.append(
                "\n"
                f"• #{session['id']} — {game_label}\n"
                f"  Статус: {status}\n"
                f"  Игроков: {session['players_count']}\n"
                f"  Присоединиться: /join {session['id']}"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    finally:
        db.close()


async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /play - создание игры"""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Укажите тип игры:\n"
            "/play cities — Города\n"
            "/play killer_words — слова, которые могут убить\n"
            "/play gd_levels — уровни Geometry Dash"
        )
        return

    game_type = context.args[0].lower()
    valid_games = list(GAME_TYPE_LABELS)

    if game_type not in valid_games:
        await update.message.reply_text(
            f"Неизвестный тип игры. Доступные: {', '.join(valid_games)}"
        )
        return

    db = next(get_db())
    try:
        games = GamesSystem(db)
        session = games.create_game_session(game_type, user.id)

        text = f"""
🎮 <b>Игра создана!</b>

Тип игры: {game_type}
ID игры: {session.id}
Создатель: {user.first_name}

👥 Другие игроки могут присоединиться:
/join {session.id}

▶️ Чтобы начать игру:
/startgame {session.id}
        """
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        db.close()


async def join_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /join - присоединение к игре"""
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Используйте: /join <id_игры>")
        return

    session_id = int(context.args[0])

    db = next(get_db())
    try:
        games = GamesSystem(db)
        success = games.join_game_session(session_id, user.id)

        if success:
            await update.message.reply_text(
                f"Вы присоединились к игре #{session_id}\n"
                "Ожидайте начала игры от создателя."
            )
        else:
            await update.message.reply_text(
                "Не удалось присоединиться к игре. Возможные причины:\n"
                "• Игра уже началась\n"
                "• Вы уже участвуете в игре\n"
                "• Достигнут лимит игроков\n"
                "• Игра не найдена"
            )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        db.close()


async def start_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /startgame - начало игры"""
    user = update.effective_user

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            "Используйте: /startgame <id_игры>\n"
            "ID игры появляется после /play <тип_игры>."
        )
        return

    session_id = int(context.args[0])

    db = next(get_db())
    try:
        games = GamesSystem(db)
        success = games.start_game_session(session_id, user.id)

        if success:
            session_info = games.get_game_session_info(session_id)
            if not session_info:
                await update.message.reply_text(f"✅ Игра #{session_id} началась.")
                return

            current_player = next(
                (
                    p
                    for p in session_info["players"]
                    if p["user_id"] == session_info["current_player_id"]
                ),
                None,
            )
            current_player_text = (
                f"Пользователь #{current_player['user_id']}"
                if current_player
                else "не удалось определить"
            )

            text = f"""
🎮 <b>Игра #{session_id} началась!</b>

Тип игры: {session_info["game_type"]}
Текущий игрок: {current_player_text}
Количество игроков: {len(session_info["players"])}

💡 Текущий игрок может сделать ход:
/turn {session_id} <ваш_ход>
            """
            await update.message.reply_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(
                "Не удалось начать игру. Возможные причины:\n"
                "• Вы не участник игры\n"
                "• Игра уже началась\n"
                "• Недостаточно игроков (минимум 2)\n"
                "• Игра не найдена"
            )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        db.close()


async def game_turn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /turn - сделать ход в игре"""
    user = update.effective_user

    if len(context.args) < 2:
        await update.message.reply_text(
            "Используйте: /turn <id_игры> <ваш_ход>\n"
            "Например: /turn 1 Москва"
        )
        return

    try:
        session_id = int(context.args[0])
        turn_input = " ".join(context.args[1:])
    except ValueError:
        await update.message.reply_text("Неверный формат команды")
        return

    db = next(get_db())
    try:
        games = GamesSystem(db)
        session_info = games.get_game_session_info(session_id)

        if not session_info or session_info["status"] != "active":
            await update.message.reply_text("Игра не активна или не найдена")
            return

        if session_info["current_player_id"] != user.id:
            await update.message.reply_text("Сейчас не ваш ход")
            return

        if session_info["game_type"] == "cities":
            result = games.process_cities_turn(session_id, user.id, turn_input)
        elif session_info["game_type"] == "killer_words":
            result = games.process_killer_words_turn(session_id, user.id, turn_input)
        elif session_info["game_type"] == "gd_levels":
            result = games.process_gd_levels_turn(session_id, user.id, turn_input)
        else:
            await update.message.reply_text("Неизвестный тип игры")
            return

        if not result.get("success"):
            await update.message.reply_text(f"❌ {result.get('reason', 'Ход не принят')}")
            return

        details = []
        if "city" in result:
            details.append(f"Город: {result['city']}")
        if "word" in result:
            details.append(f"Слово: {result['word']}")
        if "level" in result:
            details.append(f"Уровень: {result['level']}")

        reward = result.get("reward", 0)
        next_player_id = result.get("next_player_id")
        await update.message.reply_text(
            "✅ Ход принят!\n"
            + ("\n".join(details) + "\n" if details else "")
            + f"Награда: {reward} монет\n"
            + f"Следующий игрок: пользователь #{next_player_id}"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        db.close()
