# commands.py
"""Trivia game command and callback handlers."""

import html
import random
import time
import uuid
import structlog
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.database import get_db
from bot.trivia.questions import TRIVIA_QUESTIONS
from bot.trivia.service import TriviaService

logger = structlog.get_logger()

TRIVIA_COINS_REWARD = 25
GAME_TIMEOUT_SECONDS = 60


async def trivia_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new trivia game in the current chat."""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    # Check if there is an active game in the chat that hasn't timed out
    active_games = context.bot_data.setdefault("active_trivia", {})
    now = time.time()
    
    if chat.id in active_games:
        game_info = active_games[chat.id]
        if now - game_info["started_at"] < GAME_TIMEOUT_SECONDS:
            await message.reply_text(
                "⚠️ В этом чате уже запущена активная викторина!\n"
                "Ответьте на неё сначала или подождите 60 секунд."
            )
            return

    # Pick a random question
    question = random.choice(TRIVIA_QUESTIONS)
    question_text = question["text"]
    
    # Shuffle options
    options = list(question["options"])
    correct_text = options[question["correct_index"]]
    random.shuffle(options)
    correct_shuffled_index = options.index(correct_text)

    # Unique game identifier
    game_id = uuid.uuid4().hex[:12]

    # Store active game info
    active_games[chat.id] = {
        "game_id": game_id,
        "question_id": question["id"],
        "question_text": question_text,
        "correct_shuffled_index": correct_shuffled_index,
        "correct_text": correct_text,
        "explanation": question["explanation"],
        "started_at": now,
    }

    # Build inline buttons (1 per row for clean display of options)
    keyboard = []
    for idx, option in enumerate(options):
        keyboard.append([
            InlineKeyboardButton(
                option,
                callback_data=f"trivia:{game_id}:{idx}"
            )
        ])
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_msg = (
        "🧠 <b>Брейн-Ринг по Канону Олеговируса!</b>\n"
        "Первый ответивший правильно забирает <b>25 монет</b>!\n\n"
        f"❓ <b>Вопрос:</b> {html.escape(question_text)}"
    )

    await message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode="HTML")
    logger.info("Trivia game started", chat_id=chat.id, game_id=game_id, question_id=question["id"])


async def trivia_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process clicks on trivia inline buttons."""
    query = update.callback_query
    if not query:
        return

    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    _, game_id, selected_idx_str = parts
    try:
        selected_idx = int(selected_idx_str)
    except ValueError:
        return

    active_games = context.bot_data.setdefault("active_trivia", {})
    game_info = active_games.get(chat.id)

    if not game_info or game_info["game_id"] != game_id:
        await query.answer("⚠️ Эта викторина уже завершилась или устарела!", show_alert=True)
        return

    correct_idx = game_info["correct_shuffled_index"]

    if selected_idx != correct_idx:
        await query.answer("❌ Неверно! Попробуйте другие варианты.", show_alert=True)
        logger.info(
            "Trivia incorrect attempt",
            chat_id=chat.id,
            user_id=user.id,
            game_id=game_id,
            selected=selected_idx,
        )
        return

    # User answered correctly! Close the game first to prevent race conditions
    active_games.pop(chat.id, None)

    # Award coins via TriviaService
    db = next(get_db())
    try:
        service = TriviaService(db)
        new_balance = service.process_correct_answer(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            coins=TRIVIA_COINS_REWARD,
            question_text=game_info["question_text"],
        )
    except Exception as e:
        logger.error("Failed to award trivia coins", error=str(e), user_id=user.id)
        await query.answer("⚠️ Ошибка при начислении награды.", show_alert=True)
        # Restore game in case of database error
        active_games[chat.id] = game_info
        return
    finally:
        db.close()

    winner_name = f"@{user.username}" if user.username else html.escape(user.first_name or "Игрок")
    
    success_text = (
        "🎉 <b>Брейн-Ринг завершён!</b>\n\n"
        f"Победитель: {winner_name} (забирает <b>+25 монет</b>!)\n"
        f"💳 Новый баланс: {new_balance} монет\n\n"
        f"❓ <b>Вопрос:</b> {html.escape(game_info['question_text'])}\n"
        f"✅ <b>Правильный ответ:</b> {html.escape(game_info['correct_text'])}\n\n"
        f"📖 <b>Справка по канону:</b> {html.escape(game_info['explanation'])}"
    )

    try:
        # Edit the message to show results and remove buttons
        await query.edit_message_text(success_text, parse_mode="HTML")
        await query.answer("🎉 Правильно! +25 монет на баланс!")
    except Exception as edit_err:
        logger.warning("Failed to edit trivia message", error=str(edit_err))
        # Fallback to direct reply if message couldn't be edited
        await context.bot.send_message(
            chat_id=chat.id,
            text=success_text,
            parse_mode="HTML"
        )
