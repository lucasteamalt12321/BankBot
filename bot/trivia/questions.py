# questions.py
"""Lore questions and dynamic distractor generator for the Olegovirus and LTL-parasite trivia game."""

import random
import re
from pathlib import Path

from bot.ai.model_manager import AIModelManager


_CANON_PATH = Path("data/canon_knowledge.txt")
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

Правила:
- Вопрос должен проверять ЗНАНИЕ канона, а не быть очевидным.
- Правильный ответ — точная цитата или факт из канона.
- Неправильные варианты — правдоподобны, но неверны.
- Не повторяй вопросы, которые уже были в этом чате (в истории нет контекста).
- Пиши строго в указанном формате, без лишнего текста.

=== КАНОН ===
{canon}
"""


_AI_QUESTIONS_FALLBACK_TEMPLATE = """Ты — генератор викторин. Придумай вопрос на тему "Команды и возможности банковского бота BankBot".
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
    try:
        if _CANON_PATH.exists():
            return _CANON_PATH.read_text(encoding="utf-8")[:max_chars].rstrip()
    except OSError:
        pass
    return ""


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


TRIVIA_QUESTIONS = [
    # ── БЛОК 1 (ПРАВИЛА) — 3 вопроса ──────────────────────────────────────
    {
        "id": 1,
        "text": "Как согласно высокому канону правил именования вселенной разрешено называть в творчестве реального Олега?",
        "correct_text": "Олег или Степан",
        "explanation": "Реального Олега в каноническом творчестве называют только 'Олег' или 'Степан'."
    },
    {
        "id": 2,
        "text": "Что из перечисленного является строго ЗАПРЕЩЁННОЙ темой в каноническом творчестве?",
        "correct_text": "Внешность и медицинские диагнозы реальных людей",
        "explanation": "Строго запрещены темы внешности, семейных обстоятельств и медицинских диагнозов."
    },
    {
        "id": 3,
        "text": "Какой уровень канонизации требует обязательного одобрения и Луки, и Олега?",
        "correct_text": "Высокий канон (🔵)",
        "explanation": "Высокий канон полностью соответствует правилам и утверждается обеими сторонами."
    },

    # ── БЛОК 2 (ИСТОРИЯ / СЮЖЕТ) — 17 вопросов ──────────────────────────
    # Глава 1: Первые треки и рождение олеговируса
    {
        "id": 4,
        "text": "Какой трек является первым документом вселенной Олеговируса?",
        "correct_text": "«Рома» (Олег, 11 декабря 2025)",
        "explanation": "Трек «Рома» от 11 декабря 2025 — самый первый документ вселенной."
    },
    {
        "id": 5,
        "text": "В каком треке впервые прозвучал термин «олеговирус»?",
        "correct_text": "«Олег, как ты задолбал» (Лука, 26 декабря 2025)",
        "explanation": "Именно там появилась строка: «Ты не Олег, ты вирус в зале, Олеговирус — твой диагноз»."
    },
    {
        "id": 6,
        "text": "Кто из сторонних участников первым внёс вклад в мифологию, написав трек «Олеговирус»?",
        "correct_text": "Рома",
        "explanation": "Рома написал трек «Олеговирус» — первый случай вклада стороннего участника."
    },
    {
        "id": 7,
        "text": "Какая статья впервые дала Олеговирусу научное описание с антигенами KHM и POST?",
        "correct_text": "«Olegovirus checkmarevus» (Лука, апрель 2026)",
        "explanation": "Статья описывает вокальные тики, антигены и 1000 личностей носителя."
    },

    # Глава 2: Появление LTL-паразита
    {
        "id": 8,
        "text": "Почему трек «Вирус LucasTeamLuke» признан неканоничным?",
        "correct_text": "Нарушает именование (LucasTeamLuke) и упоминает внешность",
        "explanation": "Трек использует LucasTeamLuke вместо «Лука»/«LucasTeam» и содержит намёки на внешность."
    },
    {
        "id": 9,
        "text": "Какая статья Олега описывает LTL-паразита с синдромами СГД и СНЧ, но требует переработки из-за внешности?",
        "correct_text": "«LukasTeamLuke sp. nov.» (средний канон, 🟡)",
        "explanation": "Статья содержит «рыжие волосы, прикус, белую кожу» — противоречит канону, ждёт переработки."
    },

    # Глава 4: Конфликт и сотрудничество
    {
        "id": 10,
        "text": "В каких отношениях состоят олеговирус и LTL-паразит согласно статье «Olegovirus checkmarevus»?",
        "correct_text": "Союзничество-конкурентство",
        "explanation": "Они находятся в отношениях «союзничества-конкурентства»."
    },
    {
        "id": 11,
        "text": "Какой трек Ромы впервые сводит обоих агентов (олеговирус и LTL-паразита) в одном пространстве?",
        "correct_text": "«Тень агента (V.2)» (апрель 2026)",
        "explanation": "Трек содержит отсылки к обоим: «кхм-кхм» Олеговируса и «забытый чайной настой» LTL-паразита. Высокий канон."
    },

    # Глава 5: Конфетная экономика
    {
        "id": 12,
        "text": "Какая базовая награда конфетами за прохождение Nine Circles?",
        "correct_text": "1 конфета за 2% прохождения",
        "explanation": "Базовое правило: 1 конфета за 2% прогресса."
    },
    {
        "id": 13,
        "text": "Сколько конфет полагается за 1% на сложных партах (61-70%) Nine Circles?",
        "correct_text": "1 конфета за 1% прохождения",
        "explanation": "Для сложных партов (61-70%) награда удваивается — 1 конфета за 1%."
    },
    {
        "id": 14,
        "text": "Кто такой «Хранитель конфет» в конфетной экономике?",
        "correct_text": "Лука (отказался от своей награды в 28 конфет)",
        "explanation": "Лука набрал 56% прогресса (≈28 конфет), но отказался от награды в пользу других."
    },
    {
        "id": 15,
        "text": "Сколько конфет получил Рома после «инфляции счастья» (умножение на 1.5, округление вверх)?",
        "correct_text": "16 конфет",
        "explanation": "После умножения всех наград на 1.5 и округления вверх: Рома — 16, Никита — 11, Антон — 5."
    },

    # Глава 6: Чайная религия
    {
        "id": 16,
        "text": "Каким священным выражением заканчиваются молитвы в Чайной религии (Teaology)?",
        "correct_text": "eight-nine",
        "explanation": "Любая молитва завершается сакральным «eight-nine»."
    },
    {
        "id": 17,
        "text": "Кто автор и создатель Чайной религии (Teaology)?",
        "correct_text": "Лука (LucasTeam, 27 апреля 2026)",
        "explanation": "Лука опубликовал катехизис культа 27 апреля. Высокий канон."
    },

    # Глава 7: Походный дневник
    {
        "id": 18,
        "text": "Какой трек Луки стал первым «бытовым» произведением в каноне (3 мая 2026)?",
        "correct_text": "«Восемь километров (походный дневник)»",
        "explanation": "Лирический репортаж о лесе, мокрых кроссах и усталости, с отсылками к чайной религии. Высокий канон."
    },

    # Глава 8: LTRS
    {
        "id": 19,
        "text": "Какие координаты (хаос; экспрессивность) у Луки в рейтинге LTRS?",
        "correct_text": "(10; 46) — ритуальный экспрессив",
        "explanation": "Лука: минимальный хаос (10), максимальная экспрессивность (46)."
    },
    {
        "id": 20,
        "text": "Кто в рейтинге LTRS имеет тип личности «мемный экспрессив»?",
        "correct_text": "Рома (23; 26)",
        "explanation": "Рома определён как «мемный экспрессив» — хаос выше среднего, экспрессивность средняя."
    },

    # ── БЛОК 4 (ГЛОССАРИЙ) — 3 вопроса ───────────────────────────────────
    {
        "id": 21,
        "text": "Что такое «антиген KHM» в терминологии Олеговируса?",
        "correct_text": "Реакция «закатывание глаз» у окружающих",
        "explanation": "Антиген KHM — один из двух антигенов Олеговируса, вызывает реакцию «закатывание глаз»."
    },
    {
        "id": 22,
        "text": "Что в глоссарии канона означает термин «Парадокс ожидания»?",
        "correct_text": "Бронь парта сгорает, его проходит Хранитель конфет",
        "explanation": "Парадокс ожидания: забронированный парт долго ждёт игрока, и в итоге его проходит Хранитель конфет."
    },
    {
        "id": 23,
        "text": "Кто в глоссарии LTRS определяется как «Пассивный изолят»?",
        "correct_text": "Саша (15; 14)",
        "explanation": "Саша: средний пассивный хаос (15), низкая экспрессивность (14) — «пассивный изолят»."
    },
]


async def generate_trivia_question() -> dict:
    """Generate a trivia question — tries AI API first, falls back to hardcoded pool.

    Returns:
        dict: A dict containing question text, shuffled options, correct option index,
              correct option text, and explanation.
    """
    ai_question = await generate_trivia_question_ai()
    if ai_question:
        return ai_question

    # Fallback: hardcoded pool
    question = random.choice(TRIVIA_QUESTIONS)
    correct_text = question["correct_text"]

    distractors_pool = [
        q["correct_text"] for q in TRIVIA_QUESTIONS if q["correct_text"] != correct_text
    ]
    fake_answers = random.sample(distractors_pool, min(3, len(distractors_pool)))

    options = [correct_text] + fake_answers
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
