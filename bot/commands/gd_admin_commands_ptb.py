"""GD Module admin commands for Telegram bot."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler
from database.database import get_db_session, Submission, PlayerStats, Level, LevelCompletion
from bot.gd.difficulty import update_hardest_level
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Pagination settings
SUBMISSIONS_PER_PAGE = 5


async def moderate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the /moderate command - show pending submissions."""
    user = update.effective_user
    
    if not user or not user.id:
        await update.message.reply_text("❌ Ошибка: не удалось определить пользователя.")
        return
    
    # Check if user is admin
    is_admin = await check_admin(context, user.id)
    if not is_admin:
        await update.message.reply_text("❌ Доступ запрещён. Только администраторы могут модерировать заявки.")
        return
    
    try:
        with get_db_session() as session:
            # Get pending submissions
            pending_submissions = session.query(Submission).filter_by(status='pending').all()
            
            if not pending_submissions:
                await update.message.reply_text(
                    "✅ Все заявки обработаны! Новых заявок нет."
                )
                return
            
            # Show first page
            await show_pending_submissions(update, context, page=0)
            
    except Exception as e:
        logger.error(f"Error in /moderate: {e}")
        await update.message.reply_text(
            "❌ Ошибка при загрузке заявок. Попробуйте позже."
        )


async def show_pending_submissions(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0
) -> None:
    """Show a page of pending submissions with inline buttons."""
    try:
        with get_db_session() as session:
            # Get total count
            total_count = session.query(Submission).filter_by(status='pending').count()
            
            # Calculate pagination
            total_pages = (total_count + SUBMISSIONS_PER_PAGE - 1) // SUBMISSIONS_PER_PAGE
            page = max(0, min(page, total_pages - 1))
            
            # Get submissions for this page
            offset = page * SUBMISSIONS_PER_PAGE
            pending_submissions = (
                session.query(Submission)
                .filter_by(status='pending')
                .order_by(Submission.submitted_at.desc())
                .offset(offset)
                .limit(SUBMISSIONS_PER_PAGE)
                .all()
            )
            
            if not pending_submissions:
                await update.message.reply_text(
                    "✅ Все заявки обработаны! Новых заявок нет."
                )
                return
            
            # Build message
            message_lines = ["🎮 **Geometry Dash - Модерация заявок**"]
            message_lines.append(f"Страница {page + 1}/{total_pages} ({total_count} заявок)")
            message_lines.append("")
            
            for submission in pending_submissions:
                level_name = submission.level_name or f"ID: {submission.level_id}"
                message_lines.append(
                    f"📝 Заявка #{submission.id}\n"
                    f"👤 Пользователь: {submission.username or submission.user_id}\n"
                    f"🏆 Уровень: **{level_name}**\n"
                    f"📅 Отправлено: {submission.submitted_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"📄 Тип: {submission.media_type}\n"
                    f"💾 File ID: `{submission.media_file_id}`"
                )
                message_lines.append("")
            
            # Build inline keyboard
            keyboard = []
            
            # Navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton("⬅️ Назад", callback_data=f"gd_moderate_page_{page - 1}")
                )
            if page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton("➡️ Вперёд", callback_data=f"gd_moderate_page_{page + 1}")
                )
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Action buttons for first submission
            if pending_submissions:
                first_submission = pending_submissions[0]
                keyboard.append([
                    InlineKeyboardButton("✅ Подтвердить", callback_data=f"gd_moderate_approve_{first_submission.id}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"gd_moderate_reject_{first_submission.id}")
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send or edit message
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    "\n".join(message_lines),
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "\n".join(message_lines),
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
    except Exception as e:
        logger.error(f"Error showing pending submissions: {e}")
        if update.callback_query:
            await update.callback_query.answer("❌ Ошибка при загрузке заявок")
        else:
            await update.message.reply_text("❌ Ошибка при загрузке заявок")


async def moderate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks for moderation."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("gd_moderate_page_"):
        # Pagination
        page = int(data.split("_")[-1])
        await show_pending_submissions(update, context, page=page)
        
    elif data.startswith("gd_moderate_approve_"):
        # Approve submission
        submission_id = int(data.split("_")[-1])
        await approve_submission(update, context, submission_id)
        
    elif data.startswith("gd_moderate_reject_"):
        # Reject submission
        submission_id = int(data.split("_")[-1])
        await reject_submission(update, context, submission_id)


async def approve_submission(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    submission_id: int
) -> None:
    """Approve a submission."""
    try:
        with get_db_session() as session:
            submission = session.query(Submission).filter_by(id=submission_id).first()
            
            if not submission:
                await update.callback_query.edit_message_text(
                    "❌ Заявка не найдена."
                )
                return
            
            # Update submission
            submission.status = 'approved'
            submission.reviewed_at = datetime.utcnow()
            submission.reviewed_by = update.effective_user.id
            
            # Update player stats
            player_stats = session.query(PlayerStats).filter_by(user_id=submission.user_id).first()
            if player_stats:
                player_stats.total_approved += 1
            
            # Update hardest level
            if submission.level_id:
                update_hardest_level(submission.user_id, submission.level_id)
            
            # Update level completion
            if submission.level_id:
                completion = session.query(LevelCompletion).filter_by(
                    user_id=submission.user_id,
                    level_id=submission.level_id
                ).first()
                if not completion:
                    completion = LevelCompletion(
                        user_id=submission.user_id,
                        level_id=submission.level_id
                    )
                    session.add(completion)
            
            session.commit()
            
            await update.callback_query.edit_message_text(
                f"✅ **Заявка #{submission_id} подтверждена!**\n\n"
                f"Пользователь: {submission.username or submission.user_id}\n"
                f"Уровень: {submission.level_name or submission.level_id}\n"
                f"Тип: {submission.media_type}"
            )
            
            # Show next page
            await show_pending_submissions(update, context, page=0)
            
    except Exception as e:
        logger.error(f"Error approving submission {submission_id}: {e}")
        await update.callback_query.edit_message_text(
            "❌ Ошибка при подтверждении заявки."
        )


async def reject_submission(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    submission_id: int
) -> None:
    """Reject a submission."""
    try:
        with get_db_session() as session:
            submission = session.query(Submission).filter_by(id=submission_id).first()
            
            if not submission:
                await update.callback_query.edit_message_text(
                    "❌ Заявка не найдена."
                )
                return
            
            # Update submission
            submission.status = 'rejected'
            submission.reviewed_at = datetime.utcnow()
            submission.reviewed_by = update.effective_user.id
            submission.notes = "Отклонено администратором"
            
            session.commit()
            
            await update.callback_query.edit_message_text(
                f"❌ **Заявка #{submission_id} отклонена!**\n\n"
                f"Пользователь: {submission.username or submission.user_id}\n"
                f"Уровень: {submission.level_name or submission.level_id}\n"
                f"Тип: {submission.media_type}"
            )
            
            # Show next page
            await show_pending_submissions(update, context, page=0)
            
    except Exception as e:
        logger.error(f"Error rejecting submission {submission_id}: {e}")
        await update.callback_query.edit_message_text(
            "❌ Ошибка при отклонении заявки."
        )


async def check_admin(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Check if user is admin."""
    # TODO: Implement proper admin check using AdminSystem
    # For now, check against config
    from src.config import settings
    return user_id == settings.ADMIN_TELEGRAM_ID


def get_moderate_handler():
    """Return handler for /moderate command."""
    return [
        CommandHandler("moderate", moderate_command),
        CallbackQueryHandler(moderate_callback, pattern=r"^gd_moderate_.*$")
    ]
