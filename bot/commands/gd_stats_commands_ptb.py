"""GD Module statistics commands for Telegram bot."""
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from database.database import get_db_session, Level, PlayerStats, LevelCompletion, Submission
from bot.gd.difficulty import calculate_difficulty_score
from sqlalchemy import func, desc
import logging

logger = logging.getLogger(__name__)


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show top-100 levels leaderboard."""
    try:
        with get_db_session() as session:
            # Get all levels ordered by position
            levels = (
                session.query(Level)
                .filter(Level.position <= 100)
                .order_by(Level.position)
                .limit(20)  # Show top 20
                .all()
            )
            
            if not levels:
                await update.message.reply_text(
                    "📊 Топ-100 уровней пуст. Администратор ещё не добавил уровни."
                )
                return
            
            # Build message
            message_lines = ["🏆 **Geometry Dash - Топ-20 уровней**\n"]
            
            for level in levels:
                # Count completions
                completion_count = (
                    session.query(LevelCompletion)
                    .filter_by(level_id=level.id)
                    .count()
                )
                
                difficulty_score = calculate_difficulty_score(level)
                
                message_lines.append(
                    f"**#{level.position}** {level.name}\n"
                    f"   💪 Сложность: {difficulty_score}/100\n"
                    f"   ✅ Прохождений: {completion_count}"
                )
            
            message_lines.append("\n_Используйте /my_stats для просмотра своей статистики_")
            
            await update.message.reply_text(
                "\n".join(message_lines),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in /leaderboard: {e}")
        await update.message.reply_text(
            "❌ Ошибка при загрузке топа уровней."
        )


async def my_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's personal statistics."""
    user = update.effective_user
    
    if not user or not user.id:
        await update.message.reply_text("❌ Ошибка: не удалось определить пользователя.")
        return
    
    try:
        with get_db_session() as session:
            # Get player stats
            player_stats = session.query(PlayerStats).filter_by(user_id=user.id).first()
            
            if not player_stats:
                await update.message.reply_text(
                    "📊 У вас пока нет статистики.\n\n"
                    "Отправьте своё первое прохождение через /submit!"
                )
                return
            
            # Get hardest level
            hardest_level = None
            if player_stats.hardest_level_id:
                hardest_level = session.query(Level).filter_by(id=player_stats.hardest_level_id).first()
            
            # Get total submissions
            total_submissions = (
                session.query(Submission)
                .filter_by(user_id=user.id)
                .count()
            )
            
            pending_submissions = (
                session.query(Submission)
                .filter_by(user_id=user.id, status='pending')
                .count()
            )
            
            rejected_submissions = (
                session.query(Submission)
                .filter_by(user_id=user.id, status='rejected')
                .count()
            )
            
            # Get completed levels
            completed_levels = (
                session.query(LevelCompletion)
                .filter_by(user_id=user.id)
                .count()
            )
            
            # Build message
            message_lines = [
                f"📊 **Статистика {user.first_name}**\n",
                f"🏆 **Хардест:** {hardest_level.name if hardest_level else 'Нет'} "
                f"(позиция {hardest_level.position if hardest_level else 'N/A'})",
                f"✅ **Подтверждённых прохождений:** {player_stats.total_approved}",
                f"📝 **Всего заявок:** {total_submissions}",
                f"⏳ **На модерации:** {pending_submissions}",
                f"❌ **Отклонено:** {rejected_submissions}",
                f"🎮 **Пройдено уровней:** {completed_levels}",
            ]
            
            # Calculate success rate
            if total_submissions > 0:
                success_rate = (player_stats.total_approved / total_submissions) * 100
                message_lines.append(f"📈 **Процент одобрения:** {success_rate:.1f}%")
            
            await update.message.reply_text(
                "\n".join(message_lines),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in /my_stats: {e}")
        await update.message.reply_text(
            "❌ Ошибка при загрузке статистики."
        )


async def player_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show another player's statistics."""
    # Check if user mentioned someone
    if not update.message.entities or len(update.message.entities) == 0:
        await update.message.reply_text(
            "❌ Укажите пользователя: `/player_stats @username`",
            parse_mode='Markdown'
        )
        return
    
    # Get mentioned user
    mentioned_user = None
    for entity in update.message.entities:
        if entity.type == "mention":
            # Extract username from message
            username = update.message.text[entity.offset:entity.offset + entity.length].lstrip('@')
            mentioned_user = username
            break
        elif entity.type == "text_mention":
            mentioned_user = entity.user.id
            break
    
    if not mentioned_user:
        await update.message.reply_text(
            "❌ Не удалось найти упомянутого пользователя."
        )
        return
    
    try:
        with get_db_session() as session:
            # Find player by username or user_id
            if isinstance(mentioned_user, int):
                player_stats = session.query(PlayerStats).filter_by(user_id=mentioned_user).first()
            else:
                # Find by username in submissions
                submission = (
                    session.query(Submission)
                    .filter(Submission.username.ilike(f"%{mentioned_user}%"))
                    .first()
                )
                if not submission:
                    await update.message.reply_text(
                        f"❌ Пользователь @{mentioned_user} не найден в базе данных."
                    )
                    return
                
                player_stats = session.query(PlayerStats).filter_by(user_id=submission.user_id).first()
            
            if not player_stats:
                await update.message.reply_text(
                    "📊 У пользователя пока нет статистики."
                )
                return
            
            # Get hardest level
            hardest_level = None
            if player_stats.hardest_level_id:
                hardest_level = session.query(Level).filter_by(id=player_stats.hardest_level_id).first()
            
            # Get completed levels
            completed_levels = (
                session.query(LevelCompletion)
                .filter_by(user_id=player_stats.user_id)
                .count()
            )
            
            # Build message
            message_lines = [
                "📊 **Статистика игрока**\n",
                f"🏆 **Хардест:** {hardest_level.name if hardest_level else 'Нет'} "
                f"(позиция {hardest_level.position if hardest_level else 'N/A'})",
                f"✅ **Подтверждённых прохождений:** {player_stats.total_approved}",
                f"🎮 **Пройдено уровней:** {completed_levels}",
            ]
            
            await update.message.reply_text(
                "\n".join(message_lines),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in /player_stats: {e}")
        await update.message.reply_text(
            "❌ Ошибка при загрузке статистики игрока."
        )


def get_stats_handlers():
    """Return handlers for statistics commands."""
    return [
        CommandHandler("leaderboard", leaderboard_command),
        CommandHandler("my_stats", my_stats_command),
        CommandHandler("player_stats", player_stats_command),
    ]
