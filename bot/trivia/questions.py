# questions.py
"""Lore questions and dynamic distractor generator for the Olegovirus and LTL-parasite trivia game."""

import random

TRIVIA_QUESTIONS = [
    {
        "id": 1,
        "text": "Как согласно высокому канону правил именования вселенной разрешено называть в творчестве реального Олега?",
        "correct_text": "Степан (или Олег)",
        "explanation": "Реального Олега в каноническом творчестве называют только 'Олег' или 'Степан'."
    },
    {
        "id": 2,
        "text": "Что из перечисленного является строго ЗАПРЕЩЕННОЙ темой в каноническом творчестве по правилам вселенной?",
        "options": [
            "Сахарная экономика",
            "Реальные медицинские диагнозы",
            "Чайные молитвы",
            "Коэффициенты LTRS"
        ],
        "correct_text": "Реальные медицинские диагнозы",
        "explanation": "Строго запрещены темы реальной внешности, семейных обстоятельств и медицинских диагнозов."
    },
    {
        "id": 3,
        "text": "Каким термином называют вымышленный вирус во вселенной, имеющий вокальные тики 'кхм-кхм', 'бум-бум' и антигены KHM/POST?",
        "correct_text": "Олеговирус (Olegovirus checkmarevus)",
        "explanation": "Это Олеговирус. Вокальные тики и личности вроде Ивана/Олега-диктатора относятся к нему."
    },
    {
        "id": 4,
        "text": "Что такое СГД в симптоматике вымышленного LTL-паразита?",
        "correct_text": "Синдром громкостной дисрегуляции",
        "explanation": "СГД — это синдром громкостной дисрегуляции (когда персонаж говорит слишком тихо или слишком громко)."
    },
    {
        "id": 5,
        "text": "Как называется синдром навязчивого чаепития у LTL-паразита, когда он некстати произносит название горячего напитка?",
        "correct_text": "СНЧ (синдром навязчивого чаепития)",
        "explanation": "Это СНЧ — синдром навязчивого чаепития (когда персонаж внезапно говорит 'чай' или 'кофе')."
    },
    {
        "id": 6,
        "text": "Каким священным выражением традиционно заканчиваются молитвы в Чайной религии (Teaology)?",
        "correct_text": "eight-nine",
        "explanation": "Молитвы в Чайной религии заканчиваются фразой 'eight-nine'."
    },
    {
        "id": 7,
        "text": "Что означает священное числовое выражение 'eight-nine' в Чайной религии?",
        "options": [
            "8 священных чашек и 9 ложек сахара",
            "8 минут заварки и 9 глотков",
            "8 священных напитков и один неопределимый",
            "8 кругов Nine Circles и 9 конфет"
        ],
        "correct_text": "8 священных напитков и один неопределимый",
        "explanation": "'Eight-nine' символизирует 8 священных напитков и 1 неопределимый."
    },
    {
        "id": 8,
        "text": "Какая базовая награда конфетами установлена за прохождение Nine Circles в конфетной экономике?",
        "correct_text": "1 конфета за 2% прохождения",
        "explanation": "Базовое правило конфетной экономики: 1 конфета выдается за 2% прогресса."
    },
    {
        "id": 9,
        "text": "В конфетной экономике 'инфляция счастья' — это умножение наград конфетами на какой коэффициент?",
        "correct_text": "1.5 с округлением вверх",
        "explanation": "Инфляция счастья умножает конфетные награды на коэффициент 1.5 с округлением вверх."
    },
    {
        "id": 10,
        "text": "Как в LTRS (LucasTeam Rating System) характеризуется тип личности реального Луки?",
        "correct_text": "Ритуальный экспрессив",
        "explanation": "Согласно LTRS, тип личности Луки — 'ритуальный экспрессив'."
    },
    {
        "id": 11,
        "text": "Как в LTRS (LucasTeam Rating System) характеризуется тип личности реального Олега?",
        "correct_text": "Хаотичный провокатор",
        "explanation": "В LTRS тип личности Олега определен как 'хаотичный провокатор'."
    },
    {
        "id": 12,
        "text": "Что происходит при 'Парадоксе ожидания' в конфетной экономике?",
        "correct_text": "Бронь сгорает, и парт проходит Хранитель конфет",
        "explanation": "Забронированный парт долго ждет игрока, а в итоге его проходит и забирает награду Хранитель конфет."
    },
    {
        "id": 13,
        "text": "Какой уровень канонизации согласно правилам требует ОБЯЗАТЕЛЬНОГО одобрения как со стороны Луки, так и со стороны Олега?",
        "correct_text": "Высокий канон (одобрен обоими авторами)",
        "explanation": "Высокий канон полностью соответствует правилам и в обязательном порядке утверждается обеими сторонами."
    },
    {
        "id": 14,
        "text": "Какое обращение к Луке строго запрещено использовать в качестве личного творческого имени по правилам канона?",
        "correct_text": "LucasTeamLuke (только Telegram-ник)",
        "explanation": "LucasTeamLuke — это только технический юзернейм в Telegram, творческое обращение к Луке по этому нику запрещено."
    },
    {
        "id": 15,
        "text": "Кто в LTRS (LucasTeam Rating System) имеет тип личности 'молчаливый обидчик'?",
        "correct_text": "Андрей (молчаливый обидчик)",
        "explanation": "Согласно LTRS, тип личности Андрея — 'молчаливый обидчик'."
    }
]


def generate_trivia_question() -> dict:
    """Select a random question and dynamically generate 3 fake options from the other questions.

    Returns:
        dict: A dict containing question text, shuffled options, correct option index,
              correct option text, and explanation.
    """
    question = random.choice(TRIVIA_QUESTIONS)
    correct_text = question["correct_text"]

    # Gather all other correct answers to use as distractors
    distractors_pool = [
        q["correct_text"] for q in TRIVIA_QUESTIONS if q["correct_text"] != correct_text
    ]

    # Select 3 unique random fake answers
    fake_answers = random.sample(distractors_pool, min(3, len(distractors_pool)))

    # Combine and shuffle
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

