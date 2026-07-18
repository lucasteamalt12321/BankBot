"""D&D Message Handler — intercepts messages during active D&D sessions."""

import re
import random
import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from database.database import DndSession, DndCharacter
from core.systems.dnd_ai_master import DndAiMaster
from core.systems.dnd_system import DndSystem

logger = logging.getLogger(__name__)


QUESTION_RU = r"^(что|как|где|кто|почему|зачем|сколько|может|можна|можно|есть\s+ли|когда)\b"
QUESTION_EN = r"^(what|how|where|who|why|which|can|could|is\s+there|when)\b"
DICE_PATTERN = r"\b(\d*)[dк](\d+)([+-]\d+)?\b"


def classify_message(text: str) -> str:
    if not text:
        return "action"
    text_lower = text.strip().lower()
    if re.search(DICE_PATTERN, text_lower):
        return "dice"
    if re.match(QUESTION_RU, text_lower) or re.match(QUESTION_EN, text_lower):
        return "question"
    return "action"


def parse_dice(text: str) -> Optional[dict]:
    match = re.search(DICE_PATTERN, text)
    if not match:
        return None
    count_str = match.group(1)
    count = int(count_str) if count_str else 1
    sides = int(match.group(2))
    mod_str = match.group(3)
    modifier = int(mod_str) if mod_str else 0
    valid_sides = {4, 6, 8, 10, 12, 20, 100}
    if sides not in valid_sides:
        return None
    return {"count": count, "sides": sides, "modifier": modifier}


def find_active_session(db: Session, user_id: int) -> Optional[DndSession]:
    as_master = db.query(DndSession).filter(
        DndSession.master_id == user_id,
        DndSession.status == "active",
    ).first()
    if as_master:
        return as_master
    as_player = db.query(DndSession).join(DndCharacter).filter(
        DndCharacter.player_id == user_id,
        DndSession.status == "active",
    ).first()
    return as_player


def find_character(db: Session, session_id: int, user_id: int) -> Optional[DndCharacter]:
    return db.query(DndCharacter).filter(
        DndCharacter.session_id == session_id,
        DndCharacter.player_id == user_id,
    ).first()


async def handle_dnd_message(update: Update, context: ContextTypes.DEFAULT_TYPE, get_db):
    if not update.message or not update.message.text:
        return False

    user = update.effective_user
    text = update.message.text.strip()

    db: Session = next(get_db())
    try:
        session = find_active_session(db, user.id)
        if not session:
            return False

        character = find_character(db, session.id, user.id)
        character_id = character.id if character else None

        ai = DndAiMaster(db)
        msg_type = classify_message(text)

        if msg_type == "dice":
            parsed = parse_dice(text)
            if parsed:
                total_roll = sum(
                    random.randint(1, parsed["sides"])
                    for _ in range(parsed["count"])
                ) + parsed["modifier"]
                dice_text = f"{parsed['count']}d{parsed['sides']}"
                if parsed["modifier"]:
                    sign = "+" if parsed["modifier"] > 0 else ""
                    dice_text += f"{sign}{parsed['modifier']}"
                answer = await ai.process_dice_roll(
                    session.id, user.id, total_roll, dice_text, "",
                    character_id=character_id,
                )
            else:
                dnd = DndSystem(db)
                dice_roll = dnd.roll_preview("d20", 1)
                total = sum(dice_roll)
                answer = await ai.process_action(
                    session.id, user.id, f"Бросок d20 = {total} ({text})",
                    character_id=character_id,
                )
        else:
            answer = await ai.process_action(
                session.id, user.id, text,
                character_id=character_id,
            )

        await update.message.reply_text(answer)
        return True
    except Exception as e:
        logger.error(f"DND message handler error: {e}")
        return False
    finally:
        db.close()
