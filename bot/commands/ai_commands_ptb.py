"""AI Commands for Phase 2 (python-telegram-bot 20.x).

Commands:
- /chat <персонаж> <текст> - диалог с персонажем (олеговирус, чай)
- /generate_prayer - генерация молитвы чайной религии
- /ask_canon <вопрос> - вопросы по канону олеговируса/LTL
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from bot.ai.model_manager import AIModelManager


logger = logging.getLogger(__name__)


# Промпты для персонажей
CHARACTER_PROMPTS = {
    "олеговирус": (
        "Ты — олеговирус, существо, которое постоянно издаёт звуки 'кхм-кхм', "
        "любит придираться к чужим текстам и ведёт себя навязчиво. "
        "Отвечай кратко, 1-2 предложения, в характере олеговируса. "
        "Используй слова 'кхм', 'заражу', 'симптомы'. "
        "Пользователь сказал: {text}"
    ),
    "чай": (
        "Ты — верховный божественный Чай, воплощение покоя и мудрости. "
        "Говори вдохновляюще, используй слова 'настой', 'eight-nine', 'кружка-алтарь'. "
        "Отвечай кратко, 1-2 предложения, в стиле мудрого наставника. "
        "Пользователь сказал: {text}"
    ),
}

# Промпт для генерации молитвы
PRAYER_PROMPT = (
    "Сочини короткую молитву в стиле чайной религии (3-4 предложения). "
    "Используй слова 'чай', 'eight-nine', 'настой', 'кружка-алтарь'. "
    "Молитва должна быть умиротворяющей или забавной. "
    "Ответь только текстом молитвы, без кавычек и пояснений."
)


class AICommandsHandler:
    """Handler for AI-powered commands."""
    
    def __init__(self):
        self.ai_manager = AIModelManager()
        self.canon_knowledge: Optional[str] = None
        self._load_canon_knowledge()
    
    def _load_canon_knowledge(self) -> None:
        """Load canon knowledge from file."""
        canon_file = Path("data/canon_knowledge.txt")
        
        if canon_file.exists():
            try:
                with open(canon_file, 'r', encoding='utf-8') as f:
                    self.canon_knowledge = f.read()
                logger.info(f"Loaded canon knowledge: {len(self.canon_knowledge)} chars")
            except Exception as e:
                logger.error(f"Failed to load canon knowledge: {e}")
                self.canon_knowledge = None
        else:
            logger.warning(f"Canon knowledge file not found: {canon_file}")
            self.canon_knowledge = None
    
    async def chat_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle /chat <персонаж> <текст> command.
        
        Usage:
            /chat олеговирус Привет!
            /chat чай Как дела?
        """
        if not update.message or not context.args:
            await update.message.reply_text(
                "❌ Использование: /chat <персонаж> <текст>\n\n"
                "Доступные персонажи:\n"
                "• олеговирус - навязчивое существо с 'кхм-кхм'\n"
                "• чай - божественный мудрый наставник"
            )
            return
        
        # Check if AI is available
        if not self.ai_manager.is_available():
            await update.message.reply_text(
                "❌ AI недоступен. Настройте HF_TOKEN или другие провайдеры в переменных окружения."
            )
            return
        
        # Parse arguments
        character = context.args[0].lower()
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Укажите текст сообщения после персонажа.\n"
                f"Пример: /chat {character} Привет!"
            )
            return
        
        user_text = " ".join(context.args[1:])
        
        # Check character
        if character not in CHARACTER_PROMPTS:
            await update.message.reply_text(
                f"❌ Неизвестный персонаж: {character}\n\n"
                "Доступные персонажи:\n"
                "• олеговирус\n"
                "• чай"
            )
            return
        
        # Send typing indicator
        await update.message.chat.send_action("typing")
        
        try:
            # Generate prompt
            prompt = CHARACTER_PROMPTS[character].format(text=user_text)
            
            # Get AI response
            user_id = update.effective_user.id if update.effective_user else None
            response = await self.ai_manager.get_response(prompt, user_id=user_id)
            
            # Format response
            character_emoji = "🦠" if character == "олеговирус" else "☕"
            reply_text = f"{character_emoji} **{character.capitalize()}:**\n\n{response.text}"
            
            if response.cached:
                reply_text += "\n\n_[из кэша]_"
            
            await update.message.reply_text(reply_text, parse_mode="Markdown")
            
            logger.info(
                f"Chat command: user={user_id}, character={character}, "
                f"provider={response.provider}, cached={response.cached}"
            )
            
        except RuntimeError as e:
            logger.error(f"AI chat error: {e}")
            await update.message.reply_text(
                "❌ Все AI-провайдеры недоступны. Попробуйте позже."
            )
        except Exception as e:
            logger.error(f"Unexpected error in chat command: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке запроса."
            )
    
    async def generate_prayer_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /generate_prayer command.
        
        Generates a prayer in the style of tea religion.
        """
        if not update.message:
            return
        
        # Check if AI is available
        if not self.ai_manager.is_available():
            await update.message.reply_text(
                "❌ AI недоступен. Настройте HF_TOKEN или другие провайдеры в переменных окружения."
            )
            return
        
        # Send typing indicator
        await update.message.chat.send_action("typing")
        
        try:
            # Get AI response
            user_id = update.effective_user.id if update.effective_user else None
            response = await self.ai_manager.get_response(PRAYER_PROMPT, user_id=user_id)
            
            # Format response
            reply_text = f"🙏 **Молитва чайной религии:**\n\n{response.text}"
            
            if response.cached:
                reply_text += "\n\n_[из кэша]_"
            
            await update.message.reply_text(reply_text, parse_mode="Markdown")
            
            logger.info(
                f"Generate prayer: user={user_id}, provider={response.provider}, "
                f"cached={response.cached}"
            )
            
        except RuntimeError as e:
            logger.error(f"AI prayer generation error: {e}")
            await update.message.reply_text(
                "❌ Все AI-провайдеры недоступны. Попробуйте позже."
            )
        except Exception as e:
            logger.error(f"Unexpected error in generate_prayer: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при генерации молитвы."
            )
    
    async def ask_canon_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """
        Handle /ask_canon <вопрос> command.
        
        Answers questions about olegovirus/LTL canon using knowledge base.
        """
        if not update.message or not context.args:
            await update.message.reply_text(
                "❌ Использование: /ask_canon <вопрос>\n\n"
                "Пример: /ask_canon Что такое олеговирус?"
            )
            return
        
        question = " ".join(context.args)
        
        # Check if canon knowledge is loaded
        if not self.canon_knowledge:
            await update.message.reply_text(
                "❌ База знаний канона не загружена. "
                "Создайте файл data/canon_knowledge.txt с информацией о каноне."
            )
            return
        
        # Check if AI is available
        if not self.ai_manager.is_available():
            # Fallback: simple keyword search
            await self._ask_canon_fallback(update, question)
            return
        
        # Send typing indicator
        await update.message.chat.send_action("typing")
        
        try:
            # Create prompt with canon knowledge
            prompt = (
                f"Ты знаток вселенной олеговируса и LTL-паразита. "
                f"Ответь на вопрос, используя следующие факты:\n\n"
                f"{self.canon_knowledge[:1000]}\n\n"  # Limit to 1000 chars
                f"Вопрос: {question}\n\n"
                f"Если ответа нет в фактах, скажи 'Не знаю, но можешь спросить у создателя'."
            )
            
            # Get AI response
            user_id = update.effective_user.id if update.effective_user else None
            response = await self.ai_manager.get_response(prompt, user_id=user_id)
            
            # Format response
            reply_text = f"📚 **Канон олеговируса/LTL:**\n\n{response.text}"
            
            if response.cached:
                reply_text += "\n\n_[из кэша]_"
            
            await update.message.reply_text(reply_text, parse_mode="Markdown")
            
            logger.info(
                f"Ask canon: user={user_id}, question={question[:50]}, "
                f"provider={response.provider}, cached={response.cached}"
            )
            
        except RuntimeError as e:
            logger.error(f"AI ask_canon error: {e}")
            # Fallback to keyword search
            await self._ask_canon_fallback(update, question)
        except Exception as e:
            logger.error(f"Unexpected error in ask_canon: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Произошла ошибка при поиске ответа."
            )
    
    async def _ask_canon_fallback(self, update: Update, question: str) -> None:
        """Fallback: simple keyword search in canon knowledge."""
        if not self.canon_knowledge:
            await update.message.reply_text(
                "❌ База знаний недоступна и AI не настроен."
            )
            return
        
        # Simple keyword search
        question_lower = question.lower()
        lines = self.canon_knowledge.split('\n')
        
        relevant_lines = []
        for line in lines:
            if any(word in line.lower() for word in question_lower.split()):
                relevant_lines.append(line.strip())
        
        if relevant_lines:
            answer = "\n".join(relevant_lines[:5])  # Max 5 lines
            await update.message.reply_text(
                f"📚 **Найдено в каноне:**\n\n{answer}\n\n"
                f"_[простой поиск, AI недоступен]_"
            )
        else:
            await update.message.reply_text(
                "❓ Не нашёл ответа в базе знаний. "
                "Попробуй переформулировать вопрос или спроси у создателя."
            )


# Create handler instance
ai_commands_handler = AICommandsHandler()


# Command handlers for registration
async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wrapper for chat command."""
    await ai_commands_handler.chat_command(update, context)


async def generate_prayer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wrapper for generate_prayer command."""
    await ai_commands_handler.generate_prayer_command(update, context)


async def ask_canon_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wrapper for ask_canon command."""
    await ai_commands_handler.ask_canon_command(update, context)


def register_ai_commands(application) -> None:
    """Register AI commands with the application."""
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("generate_prayer", generate_prayer_command))
    application.add_handler(CommandHandler("ask_canon", ask_canon_command))
    
    logger.info("AI commands registered: /chat, /generate_prayer, /ask_canon")
