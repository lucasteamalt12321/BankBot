"""D&D AI Master commands for Telegram bot."""

import logging
import random
from typing import Optional
from datetime import datetime, timezone, timedelta

import structlog
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from database.database import get_db, DndSession, DndCharacter, DndSessionLog
from core.systems.dnd_ai_master import DndAiMaster
from core.systems.dnd_system import DndSystem
from core.systems.dnd_document_parser import DndDocumentParser

logger = structlog.get_logger()


async def dnd_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new D&D session: /dnd_start [название]"""
    user = update.effective_user

    db: Session = next(get_db())
    try:
        existing = db.query(DndSession).filter(
            DndSession.master_id == user.id,
            DndSession.status.in_(["planning", "active"]),
        ).first()
        if existing:
            await update.message.reply_text(
                f"❌ У вас уже есть активная сессия \"{existing.name}\" (#{existing.id}).\n"
                f"Сначала завершите её: /dnd_stop"
            )
            return

        name = " ".join(context.args) if context.args else f"Кампания {user.first_name}"
        session = DndSession(
            master_id=user.id,
            name=name,
            status="active",
            started_at=datetime.now(timezone.utc),
            ai_system_prompt=None,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        text = (
            f"🎲 <b>D&D сессия запущена!</b>\n\n"
            f"Название: {name}\n"
            f"ID: #{session.id}\n\n"
            f"📖 <b>Как играть:</b>\n"
            f"• Просто пиши действия — бот поймёт\n"
            f"• Кидай кубики: <code>d20</code>, <code>2d6+3</code>\n"
            f"• Загрузи книгу: отправь PDF/DOCX/TXT\n"
            f"• Загрузи персонажа: отправь файл с пометкой \"персонаж\"\n\n"
            f"🛑 Остановить: /dnd_stop\n"
            f"📊 Статус: /dnd_status\n"
            f"✏️ Исправить: /dnd_fix <текст>"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error("dnd_start_command", error=str(e))
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def dnd_stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause/stop D&D session: /dnd_stop"""
    user = update.effective_user

    db: Session = next(get_db())
    try:
        session = db.query(DndSession).filter(
            DndSession.master_id == user.id,
            DndSession.status == "active",
        ).first()
        if not session:
            await update.message.reply_text("❌ Нет активной D&D сессии.")
            return

        session.status = "paused"
        session.paused_at = datetime.now(timezone.utc)
        db.commit()

        await update.message.reply_text(
            "⏸ <b>Сессия приостановлена.</b>\n"
            "Прогресс сохранён. Чтобы продолжить: /dnd_start\n"
            "Чтобы удалить: /dnd_delete (только если уверены)",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error("dnd_stop_command", error=str(e))
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def dnd_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show D&D session status: /dnd_status"""
    user = update.effective_user

    db: Session = next(get_db())
    try:
        session = db.query(DndSession).filter(
            DndSession.master_id == user.id,
            DndSession.status.in_(["active", "paused"]),
        ).first()
        if not session:
            session = db.query(DndSession).join(DndCharacter).filter(
                DndCharacter.player_id == user.id,
                DndSession.status.in_(["active", "paused"]),
            ).first()
        if not session:
            await update.message.reply_text("📭 Нет активных D&D сессий. Используйте /dnd_start")
            return

        characters = db.query(DndCharacter).filter(
            DndCharacter.session_id == session.id,
            DndCharacter.is_active,
        ).all()

        char_lines = []
        for c in characters:
            hp = f"❤️ {c.hit_points}/{c.max_hit_points}" if c.hit_points is not None else "❤️ ?"
            ac = f"🛡️ КБ {c.armor_class}" if c.armor_class else ""
            char_lines.append(f"  • <b>{c.name}</b> ({c.character_class}, ур.{c.level}) {hp} {ac}")

        log_count = db.query(DndSessionLog).filter(
            DndSessionLog.session_id == session.id,
        ).count()

        status_icon = "▶️" if session.status == "active" else "⏸"
        text = (
            f"{status_icon} <b>{session.name}</b> (#{session.id})\n\n"
            f"📖 Сцена: {session.current_scene or 'Новая игра'}\n"
            f"📝 Событий в логе: {log_count}\n"
            f"📚 Книга загружена: {'Да' if session.book_content else 'Нет'}\n\n"
        )

        if char_lines:
            text += "👥 <b>Персонажи:</b>\n" + "\n".join(char_lines) + "\n"
        else:
            text += "👥 Нет персонажей\n"

        if session.last_ai_response:
            text += f"\n💬 <b>Последнее событие:</b>\n{session.last_ai_response[:300]}"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error("dnd_status_command", error=str(e))
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def dnd_fix_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fix AI misunderstanding: /dnd_fix <исправление>"""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "❌ Используйте: /dnd_fix <что нужно исправить>\n"
            'Пример: /dnd_fix "На самом деле я открывал дверь, а не осматривал комнату"'
        )
        return

    fix_text = " ".join(context.args)

    db: Session = next(get_db())
    try:
        session = db.query(DndSession).filter(
            DndSession.master_id == user.id,
            DndSession.status == "active",
        ).first()
        if not session:
            await update.message.reply_text("❌ Нет активной D&D сессии.")
            return

        ai = DndAiMaster(db)
        result = await ai.apply_fix(session.id, user.id, fix_text)
        await update.message.reply_text(result)
    except Exception as e:
        logger.error("dnd_fix_command", error=str(e))
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def dnd_roll_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Roll dice: /dnd_roll <dice> [purpose]"""
    if not context.args:
        await update.message.reply_text(
            "❌ Используйте: /dnd_roll <кубик> [цель]\n"
            "Примеры:\n"
            "  /dnd_roll d20\n"
            "  /dnd_roll 2d6+3\n"
            '  /dnd_roll d20 "Проверка восприятия"'
        )
        return

    user = update.effective_user
    dice_str = context.args[0]
    purpose = " ".join(context.args[1:]) if len(context.args) > 1 else None

    db: Session = next(get_db())
    try:
        session = db.query(DndSession).join(DndCharacter).filter(
            DndCharacter.player_id == user.id,
            DndSession.status == "active",
        ).first()
        if not session:
            session = db.query(DndSession).filter(
                DndSession.master_id == user.id,
                DndSession.status == "active",
            ).first()

        if "d" not in dice_str:
            await update.message.reply_text("❌ Неверный формат. Используйте: d20, 2d6+3")
            return

        dice_str = dice_str.replace(" ", "")
        count = 1
        if dice_str[0].isdigit():
            parts = dice_str.split("d", 1)
            count = int(parts[0])
            dice_str = "d" + parts[1]
        # parse type
        dice_type = "d20"
        modifier = 0
        if "+" in dice_str:
            dice_type, mod_str = dice_str.split("+")
            modifier = int(mod_str)
        elif "-" in dice_str:
            dice_type, mod_str = dice_str.split("-")
            modifier = -int(mod_str)
        else:
            dice_type = dice_str

        valid = ["d4", "d6", "d8", "d10", "d12", "d20", "d100"]
        if dice_type not in valid:
            await update.message.reply_text(f"❌ Неверный кубик. Доступны: {', '.join(valid)}")
            return

        results = [random.randint(1, int(dice_type[1:])) for _ in range(count)]
        total = sum(results) + modifier

        text = (
            f"🎲 <b>Бросок</b>\n"
            f"Кубик: {count}{dice_type}{'+' + str(modifier) if modifier > 0 else '-' + str(-modifier) if modifier < 0 else ''}\n"
            f"{'Цель: ' + purpose if purpose else ''}\n"
            f"Результат: {', '.join(map(str, results))}\n"
            f"<b>Итог: {total}</b>"
        )

        if session:
            ai = DndAiMaster(db)
            comment = await ai.process_dice_roll(
                session.id, user.id, total,
                f"{count}{dice_type}",
                purpose or "",
            )
            text += f"\n\n{comment}"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error("dnd_roll_command", error=str(e))
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    finally:
        db.close()


async def dnd_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show D&D help: /dnd"""
    text = (
        "🎲 <b>D&D ИИ-Мастер</b>\n\n"
        "<b>Команды:</b>\n"
        "  /dnd_start [название] — начать сессию\n"
        "  /dnd_stop — приостановить\n"
        "  /dnd_status — сводка сессии\n"
        "  /dnd_roll <кубик> [цель] — бросок\n"
        "  /dnd_fix <текст> — исправить ИИ\n\n"
        "<b>Как играть:</b>\n"
        "  • Просто пиши что делаешь — бот поймёт\n"
        "  • Кидай кубики: <code>d20</code>, <code>2d6+3</code>\n"
        "  • Загрузи книгу приключения (PDF/DOCX/TXT)\n"
        "  • Загрузи персонажа (файл + подпись \"персонаж\")\n\n"
        "🤖 ИИ-мастер использует Groq (LLaMA 3.1) "
        "с запасным HF Inference API."
    )
    await update.message.reply_text(text, parse_mode="HTML")
