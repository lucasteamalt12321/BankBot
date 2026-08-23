# questions.py
"""Lore questions and dynamic distractor generator for the Olegovirus and LTL-parasite trivia game."""

import random
import re

from bot.ai.model_manager import AIModelManager
from core.canon import load_canon_text
from core.canon.questions import TRIVIA_QUESTIONS


_ai_manager: AIModelManager | None = None


def _get_ai_manager() -> AIModelManager:
    global _ai_manager
    if _ai_manager is None:
        _ai_manager = AIModelManager()
    return _ai_manager


_AI_QUESTIONS_PROMPT = """Ты — генератор викторин по канону вселенной Олеговируса и LTL-паразита.
Используя текст канона ниже, составь один вопрос с четырьмя вариантами ответа.

Формат ответа (строго):
Вопрос: <текст вопроса>
1. <вариант>
2. <вариант>
3. <вариант>
4. <вариант>
Правильный ответ: <номер от 1 до 4>
Объяснение: <почему это правильный ответ>

ВАЖНЕЙШЕЕ ПРАВИЛО: Все четыре варианта ответа должны быть из ОДНОГО раздела канона.
Примеры:
  ПЛОХО: вопрос про треки → варианты про конфеты, чай, именование
  ХОРОШО: вопрос про треки → все варианты — разные названия треков
  ПЛОХО: вопрос про конфетную экономику → варианты про LTRS, антигены, имена
  ХОРОШО: вопрос про конфетную экономику → все варианты про конфеты и проценты

Правила:
- Вопрос должен проверять ЗНАНИЕ канона, а не быть очевидным.
- Правильный ответ — точная цитата или факт из канона.
- Неправильные варианты должны звучать ПРАВДОПОДОБНО в той же теме.
- НЕ используй имена участников (Лука, Олег, Рома, Никита и т.д.) как неправильные ответы.
- Пиши строго в указанном формате, без лишнего текста.

=== КАНОН ===
{canon}
"""


_AI_QUESTIONS_FALLBACK_TEMPLATE = """Ты — генератор викторин. Придумай вопрос на тему "Команды и возможности бота LTHub (LucasTeam Hub)".
Составь один вопрос с четырьмя вариантами ответа.

Формат ответа (строго):
Вопрос: <текст вопроса>
1. <вариант>
2. <вариант>
3. <вариант>
4. <вариант>
Правильный ответ: <номер от 1 до 4>
Объяснение: <почему это правильный ответ>
"""


def _load_canon_for_trivia(max_chars: int = 2000) -> str:
    """Load canon text for AI question generation context."""
    return load_canon_text()[:max_chars].rstrip()


def _parse_ai_questions_response(text: str) -> dict | None:
    """Parse AI response into a trivia question dict."""
    lines = text.strip().split("\n")
    question_text = ""
    options: list[str] = []
    correct_answer = ""
    explanation = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Вопрос:"):
            question_text = stripped[len("Вопрос:"):].strip()
        elif re.match(r"^[1-4]\.\s", stripped):
            options.append(re.sub(r"^[1-4]\.\s*", "", stripped))
        elif stripped.startswith("Правильный ответ:"):
            correct_answer = stripped[len("Правильный ответ:"):].strip()
        elif stripped.startswith("Объяснение:"):
            explanation = stripped[len("Объяснение:"):].strip()

    if not question_text or len(options) < 4 or not correct_answer or not explanation:
        return None

    try:
        correct_idx = int(correct_answer) - 1
    except ValueError:
        return None

    if correct_idx < 0 or correct_idx >= len(options):
        return None

    return {
        "id": 0,
        "text": question_text,
        "options": options,
        "correct_index": correct_idx,
        "correct_text": options[correct_idx],
        "explanation": explanation,
    }


async def generate_trivia_question_ai() -> dict | None:
    """Generate a trivia question using AI API. Returns None if unavailable."""
    manager = _get_ai_manager()
    if not manager.is_available():
        return None

    canon = _load_canon_for_trivia()
    if canon:
        prompt = _AI_QUESTIONS_PROMPT.format(canon=canon)
    else:
        prompt = _AI_QUESTIONS_FALLBACK_TEMPLATE

    try:
        response = await manager.get_response(prompt, max_tokens=400)
        if response and response.text:
            parsed = _parse_ai_questions_response(response.text)
            if parsed:
                return parsed
    except RuntimeError:
        pass

    return None


async def generate_trivia_question() -> dict:
    """Generate a trivia question — tries AI API first, falls back to hardcoded pool.

    Returns:
        dict: A dict containing question text, shuffled options, correct option index,
              correct option text, and explanation.
    """
    ai_question = await generate_trivia_question_ai()
    if ai_question:
        return ai_question

    # Fallback: hardcoded pool, manual distractors (or same-group if unavailable)
    question = random.choice(TRIVIA_QUESTIONS)
    correct_text = question["correct_text"]
    q_group = question.get("group", "")

    manual = question.get("distractors") or []
    if len(manual) >= 3:
        distractors_pool = random.sample(manual, 3)
    else:
        same_group = [q for q in TRIVIA_QUESTIONS if q.get("group") == q_group and q["correct_text"] != correct_text]
        other = [q for q in TRIVIA_QUESTIONS if q.get("group") != q_group and q["correct_text"] != correct_text]
        distractors_pool = [q["correct_text"] for q in same_group]
        if len(distractors_pool) < 3:
            distractors_pool += [q["correct_text"] for q in other]
        distractors_pool = random.sample(distractors_pool, min(3, len(distractors_pool)))

    options = [correct_text] + distractors_pool
    random.shuffle(options)
    correct_index = options.index(correct_text)

    return {
        "id": question["id"],
        "text": question["text"],
        "options": options,
        "correct_index": correct_index,
        "correct_text": correct_text,
        "explanation": question["explanation"],
    }
