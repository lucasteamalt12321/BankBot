"""D&D Document Upload Handler — parses books and character sheets."""

import re
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from database.database import get_db, DndSession, DndCharacter
from core.systems.dnd_document_parser import DndDocumentParser

logger = logging.getLogger(__name__)


async def handle_dnd_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message
    doc = message.document

    if not doc or not doc.file_name:
        return

    db: Session = next(get_db())
    try:
        session = db.query(DndSession).filter(
            DndSession.master_id == user.id,
            DndSession.status == "active",
        ).first()
        if not session:
            session = db.query(DndSession).join(DndCharacter).filter(
                DndCharacter.player_id == user.id,
                DndSession.status == "active",
            ).first()

        if not session:
            return

        caption = (message.caption or "").lower()
        file_ext = doc.file_name.split(".")[-1].lower() if "." in doc.file_name else ""
        allowed = {"pdf", "docx", "doc", "txt", "jpg", "jpeg", "png", "webp"}
        if file_ext not in allowed:
            await message.reply_text(f"❌ Неподдерживаемый формат: .{file_ext}. Нужен: PDF, DOCX, TXT, JPG, PNG")
            return

        file = await doc.get_file()
        file_bytes = await file.download_as_bytearray()

        parser = DndDocumentParser()
        text = parser.parse_file(bytes(file_bytes), doc.file_name)
        if not text or len(text.strip()) < 50:
            await message.reply_text("❌ Не удалось извлечь текст из файла. Файл пуст или повреждён.")
            return

        is_character_sheet = any(kw in caption for kw in ["персонаж", "character", "чар", "лист", "sheet", "stats"])

        if is_character_sheet:
            char_data = parser.extract_character_sheet(text)
            if not char_data:
                await message.reply_text(
                    "📄 Файл получен, но не удалось распознать персонажа.\n"
                    "Убедитесь, что в файле есть имя, класс, уровень и характеристики.\n"
                    "Или опишите персонажа вручную."
                )
                return

            existing = db.query(DndCharacter).filter(
                DndCharacter.session_id == session.id,
                DndCharacter.player_id == user.id,
            ).first()

            if existing:
                for key, val in char_data.items():
                    if key == "name":
                        existing.name = val
                    elif key == "race":
                        existing.race = val
                    elif key == "class":
                        existing.character_class = val
                    elif key == "level" and isinstance(val, int):
                        existing.level = val
                    elif key == "alignment":
                        existing.alignment = val
                    elif key in ("hp", "max_hp") and isinstance(val, int):
                        if key == "hp":
                            existing.hit_points = val
                        else:
                            existing.max_hit_points = val
                    elif key == "ac" and isinstance(val, int):
                        existing.armor_class = val
                    elif key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma") and isinstance(val, int):
                        stats = dict(existing.stats) if existing.stats else {}
                        stat_map = {
                            "strength": "strength", "dexterity": "dexterity",
                            "constitution": "constitution", "intelligence": "intelligence",
                            "wisdom": "wisdom", "charisma": "charisma",
                        }
                        stats[stat_map[key]] = val
                        existing.stats = stats
                existing.is_active = True
                existing.last_active_at = datetime.now(timezone.utc)
                db.commit()
                await message.reply_text(f"✅ Персонаж {existing.name} обновлён из файла!")
            else:
                stats = {
                    "strength": char_data.get("strength", 10),
                    "dexterity": char_data.get("dexterity", 10),
                    "constitution": char_data.get("constitution", 10),
                    "intelligence": char_data.get("intelligence", 10),
                    "wisdom": char_data.get("wisdom", 10),
                    "charisma": char_data.get("charisma", 10),
                }
                character = DndCharacter(
                    session_id=session.id,
                    player_id=user.id,
                    name=char_data.get("name", "Безымянный"),
                    race=char_data.get("race"),
                    character_class=char_data.get("class", "Воин"),
                    level=char_data.get("level", 1),
                    alignment=char_data.get("alignment"),
                    stats=stats,
                    hit_points=char_data.get("hp", 10),
                    max_hit_points=char_data.get("max_hp", 10),
                    armor_class=char_data.get("ac", 10),
                    is_active=True,
                    last_active_at=datetime.now(timezone.utc),
                )
                db.add(character)
                db.commit()
                await message.reply_text(
                    f"✅ Персонаж <b>{character.name}</b> создан!\n"
                    f"{character.race or ''} {character.character_class}, ур. {character.level}\n"
                    f"❤️ {character.hit_points}/{character.max_hit_points} 🛡️ КБ {character.armor_class}",
                    parse_mode="HTML",
                )
        else:
            scenes = parser.split_into_scenes(text, 10000)
            session.book_content = text
            session.current_scene = scenes[0] if scenes else text[:10000]
            session.context_summary = parser.create_summary(text, 3000)
            total_chars = len(text)
            scene_count = len(scenes)
            db.commit()
            await message.reply_text(
                f"📖 Книга загружена!\n"
                f"Файл: {doc.file_name}\n"
                f"Размер текста: ~{total_chars} символов\n"
                f"Разбито на {scene_count} сцен\n"
                f"Теперь опишите действие, и мастер начнёт игру!"
            )
    except Exception as e:
        logger.error(f"DND file upload error: {e}")
        await message.reply_text("❌ Ошибка обработки файла. Попробуйте позже.")
    finally:
        db.close()
