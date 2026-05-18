"""Game commands for python-telegram-bot."""

from telegram import Update
from telegram.ext import ContextTypes

from database.database import get_db
from core.systems.games_system import GamesSystem


async def games_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /games - информация о мини-играх"""
    text = """
[GAME] <b>Мини-игры</b>

Доступные игры:

1. <b>[CITY] Города</b>
   • Классическая игра в города
   • Назовите город на последнюю букву предыдущего
   • Награда: 5 монет за ход
   • Команды: /play cities

2. <b>[KNIFE] Слова, которые могут убить</b>
   • Придумывайте "убийственные" слова
   • Слова связанные с оружием, ядами и т.д.
   • Награда: до 15 монет за слово
   • Команды: /play killer_words

3. <b>[MUSIC] Уровни GD</b>
   • Аналог игры в города, но с уровнями Geometry Dash
   • Награда: 5 монет за ход
   • Команды: /play gd_levels

[NOTE] <b>Как играть:</b>
1. Создайте игру: /play <тип_игры>
2. Другие игроки присоединяются: /join <id_игры>
3. Начинайте игру: /startgame <id_игры>
4. Делайте ходы: /turn <ваш_ход>

[TARGET] <b>Текущие активные игры:</b>
   /games_list - список активных игр
    """
    await update.message.reply_text(text, parse_mode="HTML")


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
    valid_games = ["cities", "killer_words", "gd_levels"]

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
[GAME] <b>Игра создана!</b>

Тип игры: {game_type}
ID игры: {session.id}
Создатель: {user.first_name}

[PEOPLE] Другие игроки могут присоединиться:
/join {session.id}

/PLAY] Чтобы начать игру:
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
            if session_info:
                current_player = next(
                    (
                        p
                        for p in session_info["players"]
                        if p["user_id"] == session_info["current_player_id"]
                    ),
                    None,
                )

                if current_player:
                    text = f"""
[GAME] <b>Игра #{session_id} началась!</b>

Тип игры: {session_info["game_type"]}
Текущий игрок: Пользователь #{current_player["user_id"]}
Количество игроков: {len(session_info["players"])}

[TIP] Текущий игрок может сделать ход:
/turn {session_id} <ваш_ход>
                    """
                    await update.message.reply_text(text, parse_mode="HTML")
        else:
            await update.message.reply_text(
                "Не удалось начать игру. Возможные причины:\n"
                "• Вы не создатель игры\n"
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

        await update.message.reply_text(result.get("message", "Ход сделан"))
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {str(e)}")
    finally:
        db.close()
