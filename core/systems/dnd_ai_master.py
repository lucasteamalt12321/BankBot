"""D&D AI Master — generates narrative responses via external AI API."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from database.database import DndSession, DndCharacter, DndSessionLog, DndFix
from src.config import settings

logger = logging.getLogger(__name__)


class DndAiMaster:
    """AI Game Master for D&D sessions using external LLM providers."""

    def __init__(self, db: Session):
        self.db = db
        self._model_manager = None

    @property
    def model_manager(self):
        if self._model_manager is None:
            from bot.ai.model_manager import AIModelManager
            self._model_manager = AIModelManager()
        return self._model_manager

    def _get_session(self, session_id: int) -> Optional[DndSession]:
        return self.db.query(DndSession).filter(DndSession.id == session_id).first()

    def _get_active_players(self, session_id: int) -> list[DndCharacter]:
        return self.db.query(DndCharacter).filter(
            DndCharacter.session_id == session_id,
            DndCharacter.is_active,
        ).all()

    def _get_recent_log(self, session_id: int, limit: int = 10) -> list[DndSessionLog]:
        return self.db.query(DndSessionLog).filter(
            DndSessionLog.session_id == session_id
        ).order_by(DndSessionLog.created_at.desc()).limit(limit).all()

    def _get_fixes_context(self, session_id: int) -> str:
        fixes = self.db.query(DndFix).filter(
            DndFix.session_id == session_id,
            DndFix.applied,
        ).all()
        if not fixes:
            return ""
        parts = ["Запомненные исправления:"]
        for fix in fixes[-5:]:
            parts.append(f"- Игрок: \"{fix.original_context}\" -> Поправка: {fix.correction}")
        return "\n".join(parts)

    def build_prompt(self, session: DndSession, action_text: str) -> str:
        system_prompt = session.ai_system_prompt or settings.DND_AI_SYSTEM_PROMPT

        context_parts = [f"Инструкция: {system_prompt}"]

        if session.context_summary:
            context_parts.append(f"\nКонтекст книги/сцены:\n{session.context_summary[:3000]}")

        if session.current_scene:
            context_parts.append(f"\nТекущая сцена:\n{session.current_scene[:2000]}")

        characters = self._get_active_players(session.id)
        if characters:
            char_lines = ["\nАктивные персонажи:"]
            for c in characters:
                parts = [f"{c.name} ({c.character_class}, ур. {c.level})"]
                if c.hit_points is not None:
                    parts.append(f"ХП: {c.hit_points}/{c.max_hit_points}")
                if c.armor_class:
                    parts.append(f"КБ: {c.armor_class}")
                char_lines.append(" - " + ", ".join(parts))
            context_parts.append("\n".join(char_lines))

        fixes = self._get_fixes_context(session.id)
        if fixes:
            context_parts.append(f"\n{fixes}")

        recent = self._get_recent_log(session.id, 8)
        if recent:
            log_lines = ["\nИстория последних действий:"]
            for entry in reversed(recent):
                prefix = {
                    "player_action": "👤",
                    "ai_response": "🤖",
                    "dice_roll": "🎲",
                    "system": "⚙️",
                }.get(entry.message_type, "•")
                name = entry.character.name if entry.character else "Игрок"
                text = entry.content[:200]
                log_lines.append(f"{prefix} {name}: {text}")
            context_parts.append("\n".join(log_lines))

        context_parts.append(f"\nДействие игрока:\n{action_text}")
        context_parts.append("\n(Ответь на русском, не более 800 символов. Опиши ситуацию и дай варианты действий.)")

        return "\n".join(context_parts)

    async def process_action(self, session_id: int, player_id: int, action_text: str,
                             character_id: Optional[int] = None) -> str:
        session = self._get_session(session_id)
        if not session or session.status != "active":
            return "❌ Нет активной D&D сессии. Используйте /dnd_start чтобы начать."

        self.db.add(DndSessionLog(
            session_id=session_id,
            player_id=player_id,
            character_id=character_id,
            message_type="player_action",
            content=action_text,
        ))
        self.db.commit()

        prompt = self.build_prompt(session, action_text)

        try:
            response = await self.model_manager.get_response(
                prompt=prompt,
                user_id=player_id,
                preferred_provider="gemini",
                max_tokens=settings.DND_AI_MAX_TOKENS,
            )
            answer = response.text[:800] if response.text else "Мастер погрузился в раздумья..."
        except Exception as e:
            logger.error(f"D&D AI Master error: {e}")
            answer = "🌌 Мастер задумался... Попробуйте ещё раз или опишите своё действие иначе."

        session.last_ai_response = answer
        self.db.add(DndSessionLog(
            session_id=session_id,
            player_id=player_id,
            character_id=character_id,
            message_type="ai_response",
            content=answer,
            ai_context=prompt,
        ))
        self.db.commit()

        return answer

    async def process_dice_roll(self, session_id: int, player_id: int,
                                dice_result: int, dice_text: str, purpose: str,
                                character_id: Optional[int] = None) -> str:
        session = self._get_session(session_id)
        if not session or session.status != "active":
            return f"🎲 Результат: {dice_result} ({dice_text})"

        self.db.add(DndSessionLog(
            session_id=session_id,
            player_id=player_id,
            character_id=character_id,
            message_type="dice_roll",
            content=f"{dice_text}: {dice_result}{' (' + purpose + ')' if purpose else ''}",
        ))
        self.db.commit()

        prompt = (
            self.build_prompt(session, f"Бросок кубика: {dice_text} = {dice_result}")
            + "\n(Прокомментируй результат броска, опиши что произошло.)"
        )

        try:
            response = await self.model_manager.get_response(
                prompt=prompt,
                user_id=player_id,
                preferred_provider="gemini",
                max_tokens=settings.DND_AI_MAX_TOKENS,
            )
            answer = response.text[:800] if response.text else f"🎲 Результат: {dice_result}!"
        except Exception as e:
            logger.error(f"D&D AI Master dice error: {e}")
            answer = f"🎲 Результат: {dice_result}!"

        session.last_ai_response = answer
        self.db.add(DndSessionLog(
            session_id=session_id,
            player_id=player_id,
            character_id=character_id,
            message_type="ai_response",
            content=answer,
        ))
        self.db.commit()

        return answer

    async def apply_fix(self, session_id: int, player_id: int, correction: str,
                        character_id: Optional[int] = None) -> str:
        session = self._get_session(session_id)
        if not session:
            return "❌ Сессия не найдена."

        last_log = self.db.query(DndSessionLog).filter(
            DndSessionLog.session_id == session_id,
        ).order_by(DndSessionLog.created_at.desc()).first()

        original = last_log.content if last_log else ""

        self.db.add(DndFix(
            session_id=session_id,
            player_id=player_id,
            character_id=character_id,
            original_context=original,
            correction=correction,
        ))
        self.db.commit()

        return f"✅ Исправление запомнено: {correction}"

    def get_session_summary(self, session_id: int) -> dict:
        session = self._get_session(session_id)
        if not session:
            return {"error": "Сессия не найдена"}

        characters = self._get_active_players(session.id)
        char_list = []
        for c in characters:
            char_list.append({
                "name": c.name or "Безымянный",
                "class": c.character_class,
                "level": c.level,
                "hp": f"{c.hit_points}/{c.max_hit_points}" if c.hit_points is not None else "?",
                "ac": c.armor_class or "?",
            })

        log_count = self.db.query(DndSessionLog).filter(
            DndSessionLog.session_id == session_id
        ).count()

        return {
            "id": session.id,
            "name": session.name,
            "status": session.status,
            "scene": session.current_scene or "Не выбрана",
            "characters": char_list,
            "log_entries": log_count,
            "book_loaded": bool(session.book_content),
        }
