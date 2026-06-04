# commands.py
"""Trivia game command and poll answer handlers."""

import html
import random
import time
import structlog
from telegram import Update
from telegram.ext import ContextTypes

from database.database import get_db
from bot.trivia.questions import generate_trivia_question
from bot.trivia.service import TriviaService

logger = structlog.get_logger()

TRIVIA_COINS_REWARD = 10
GAME_TIMEOUT_SECONDS = 60


async def trivia_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new native Telegram trivia poll in the current chat."""
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

    # Pick a random question and generate distractors dynamically
    question = generate_trivia_question()
    question_text = question["text"]
    options = question["options"]
    correct_shuffled_index = question["correct_index"]
    correct_text = question["correct_text"]

    try:
        # Send native Telegram poll (Quiz type, non-anonymous so we can see the voters)
        poll_message = await context.bot.send_poll(
            chat_id=chat.id,
            question=question_text[:300],  # Telegram limit 300
            options=[opt[:100] for opt in options],  # Telegram limit 100 per option
            type="quiz",
            correct_option_id=correct_shuffled_index,
            is_anonymous=False,
            explanation=f"Справка: {question['explanation']}"[:200],  # Telegram limit 200
        )
    except Exception as poll_err:
        logger.error("Failed to send native trivia poll", error=str(poll_err))
        await message.reply_text("❌ Не удалось отправить опрос. Пожалуйста, попробуйте позже.")
        return

    # Store active game info mapped by both chat_id (for spam protection) and poll_id (for answer handling)
    game_state = {
        "chat_id": chat.id,
        "poll_message_id": poll_message.message_id,
        "question_text": question_text,
        "correct_option_id": correct_shuffled_index,
        "correct_text": correct_text,
        "explanation": question["explanation"],
        "started_at": now,
    }
    
    active_games[chat.id] = game_state
    
    active_polls = context.bot_data.setdefault("active_polls", {})
    active_polls[poll_message.poll.id] = game_state

    logger.info(
        "Trivia native poll started",
        chat_id=chat.id,
        poll_id=poll_message.poll.id,
        question_id=question["id"]
    )


async def trivia_poll_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process native Telegram poll answers."""
    poll_answer = update.poll_answer
    if not poll_answer:
        return

    poll_id = poll_answer.poll_id
    user = poll_answer.user
    if not user:
        return

    active_polls = context.bot_data.setdefault("active_polls", {})
    game_info = active_polls.get(poll_id)
    if not game_info:
        return  # Already resolved or not our poll

    selected_idx = poll_answer.option_ids[0] if poll_answer.option_ids else None
    if selected_idx is None:
        return

    correct_idx = game_info["correct_option_id"]

    if selected_idx != correct_idx:
        # Wrong answer, do nothing (other users can still attempt)
        logger.info(
            "Trivia poll incorrect attempt",
            poll_id=poll_id,
            user_id=user.id,
            selected=selected_idx,
        )
        return

    # First correct answer wins! Close the game first to prevent race conditions
    active_polls.pop(poll_id, None)
    
    active_games = context.bot_data.setdefault("active_trivia", {})
    active_games.pop(game_info["chat_id"], None)

    chat_id = game_info["chat_id"]
    poll_message_id = game_info["poll_message_id"]

    try:
        # Stop/close the poll
        await context.bot.stop_poll(chat_id=chat_id, message_id=poll_message_id)
    except Exception as stop_err:
        logger.warning("Failed to stop poll", error=str(stop_err))

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
        # Restore the game state in case of database error
        active_polls[poll_id] = game_info
        active_games[chat_id] = game_info
        return
    finally:
        db.close()

    winner_name = f"@{user.username}" if user.username else html.escape(user.first_name or "Игрок")
    
    success_text = (
        f"🎉 <b>Поздравляем!</b> {winner_name} первым ответил(а) правильно и забирает <b>+{TRIVIA_COINS_REWARD} монет</b>!\n"
        f"💳 Новый баланс: {new_balance} монет\n\n"
        f"📖 <b>Справка по канону:</b> {html.escape(game_info['explanation'])}"
    )

    try:
        # Reply under the poll message
        await context.bot.send_message(
            chat_id=chat_id,
            text=success_text,
            reply_to_message_id=poll_message_id,
            parse_mode="HTML"
        )
    except Exception as msg_err:
        logger.warning("Failed to send trivia success message", error=str(msg_err))
