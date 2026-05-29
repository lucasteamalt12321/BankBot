"""GD Module commands for Telegram bot."""
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler
from database.database import get_db_session, Submission, PlayerStats
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# States for /submit conversation
SUBMIT_SELECT_LEVEL, SUBMIT_UPLOAD_MEDIA, SUBMIT_CONFIRM = range(3)


async def submit_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the /submit command - ask user to enter level name."""
    await update.message.reply_text(
        "🎮 **Geometry Dash - Отправка прохождения**\n\n"
        "Введите название уровня (например, 'Cubes' или 'Tartarus'):"
    )
    
    return SUBMIT_SELECT_LEVEL


async def submit_select_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store level name and ask for media."""
    level_name = update.message.text.strip()
    context.user_data['submit_level'] = level_name
    
    await update.message.reply_text(
        f"Уровень: **{level_name}**\n\n"
        "Отправьте видео или фото с прохождением уровня:"
    )
    
    return SUBMIT_UPLOAD_MEDIA


async def submit_upload_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store media and ask for confirmation."""
    level_name = context.user_data.get('submit_level')
    
    media_file = None
    media_type = None
    
    if update.message.video:
        media_file = update.message.video
        media_type = 'video'
    elif update.message.document and update.message.document.mime_type.startswith('video/'):
        media_file = update.message.document
        media_type = 'video'
    elif update.message.photo:
        media_file = update.message.photo[-1]
        media_type = 'photo'
    else:
        await update.message.reply_text(
            "❌ Пожалуйста, отправьте видео или фото с прохождением."
        )
        return SUBMIT_UPLOAD_MEDIA
    
    context.user_data['submit_media'] = {
        'file_id': media_file.file_id,
        'file_size': media_file.file_size,
        'type': media_type
    }
    
    # Show preview
    if media_type == 'video':
        await update.message.reply_video(
            media_file.file_id,
            caption=f"Предпросмотр видео для уровня: {level_name}\n\n"
                    f"Размер: {media_file.file_size} байт\n\n"
                    "✅ Подтвердить отправку?\n"
                    "❌ Отменить"
        )
    else:
        await update.message.reply_photo(
            media_file.file_id,
            caption=f"Предпросмотр фото для уровня: {level_name}\n\n"
                    f"Размер: {media_file.file_size} байт\n\n"
                    "✅ Подтвердить отправку?\n"
                    "❌ Отменить"
        )
    
    return SUBMIT_CONFIRM


async def submit_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process submission confirmation."""
    user = update.message.from_user
    level_name = context.user_data.get('submit_level')
    media_data = context.user_data.get('submit_media')
    
    if update.message.text == "❌ Отменить":
        await update.message.reply_text(
            "❌ Отправка отменена.",
            parse_mode=None
        )
        return ConversationHandler.END
    
    if update.message.text != "✅ Подтвердить":
        await update.message.reply_text(
            "Пожалуйста, выберите: ✅ Подтвердить или ❌ Отменить"
        )
        return SUBMIT_CONFIRM
    
    # Save to database
    try:
        with get_db_session() as session:
            submission = Submission(
                user_id=user.id,
                username=user.username or user.full_name,
                level_name=level_name,
                media_file_id=media_data['file_id'],
                media_type=media_data['type'],
                status='pending',
                submitted_at=datetime.utcnow()
            )
            
            session.add(submission)
            session.commit()
            
            # Update player stats
            player_stats = session.query(PlayerStats).filter_by(user_id=user.id).first()
            if not player_stats:
                player_stats = PlayerStats(user_id=user.id, total_submissions=0, approved_submissions=0)
                session.add(player_stats)
            
            player_stats.total_submissions += 1
            session.commit()
            
            logger.info(f"Submission created: user={user.id}, level={level_name}, submission_id={submission.id}")
            
            await update.message.reply_text(
                f"✅ **Заявка отправлена!**\n\n"
                f"Уровень: **{level_name}**\n"
                f"Статус: **Ожидает модерации**\n\n"
                f"Ваша заявка будет рассмотрена администратором.",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error saving submission: {e}")
        await update.message.reply_text(
            "❌ Ошибка при сохранении заявки. Попробуйте позже."
        )
        return ConversationHandler.END
    
    context.user_data.clear()
    return ConversationHandler.END


async def submit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the submission."""
    await update.message.reply_text(
        "❌ Отправка отменена.",
        parse_mode=None
    )
    context.user_data.clear()
    return ConversationHandler.END


def get_gd_handlers():
    """Return handlers for GD module commands."""
    submit_handler = ConversationHandler(
        entry_points=[CommandHandler("submit", submit_command_start)],
        states={
            SUBMIT_SELECT_LEVEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, submit_select_level)
            ],
            SUBMIT_UPLOAD_MEDIA: [
                MessageHandler(
                    filters.VIDEO | filters.DOCUMENT | filters.PHOTO,
                    submit_upload_media
                )
            ],
            SUBMIT_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, submit_confirm)
            ],
        },
        fallbacks=[CommandHandler("cancel", submit_cancel)],
        per_user=True,
        per_chat=True
    )
    
    return [submit_handler]
