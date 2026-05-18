from bot.ai.service import AiLiteService, MAX_QUESTION_LENGTH


def test_ai_help_explains_free_local_mode() -> None:
    service = AiLiteService()

    text = service.help_text()

    assert "бесплатный локальный помощник" in text
    assert "без платных API" in text
    assert "небольшой" not in text
    assert "/ai" in text
    assert "/ask" in text
    assert "/ai@lt_lo_game_bot &lt;вопрос&gt;" in text
    assert "/ai@lt_lo_game_bot <вопрос>" not in text
    assert "канон Олеговируса/LTL-паразита" in text


def test_ai_answers_shop_question() -> None:
    service = AiLiteService()

    answer = service.answer("как купить товар в магазине?")

    assert "Магазин" in answer
    assert "/shop" in answer
    assert "/buy <номер>" in answer


def test_ai_answers_about_bot_question() -> None:
    service = AiLiteService()

    answer = service.answer("что это за бот?")

    assert "BankBot LucasTeam" in answer
    assert "/commands" in answer
    assert "/feedback <текст>" in answer


def test_ai_answers_feedback_question() -> None:
    service = AiLiteService()

    answer = service.answer("куда отправить жалобу или предложение")

    assert "Предложения и жалобы" in answer
    assert "/feedback <текст>" in answer


def test_ai_handles_multiple_topics_shortly() -> None:
    service = AiLiteService()

    answer = service.answer("баланс и игры")

    assert "Профиль и баланс" in answer
    assert "Игры" in answer
    assert len(answer) < 2500


def test_ai_handles_offtopic_tea_without_claiming_llm() -> None:
    service = AiLiteService()

    answer = service.answer("кофе")

    assert "оффтоп" in answer
    assert "справочник по BankBot" in answer
    assert "/commands" in answer


def test_ai_is_honest_about_limits() -> None:
    service = AiLiteService()

    answer = service.answer("ты тупой ии из палок?")

    assert "не большая нейросеть" in answer
    assert "бесплатный локальный справочник" in answer
    assert "локальный LLM" in answer


def test_ai_rejects_too_long_question() -> None:
    service = AiLiteService()

    answer = service.answer("а" * (MAX_QUESTION_LENGTH + 1))

    assert "Вопрос слишком длинный" in answer


def test_ai_fallback_suggests_commands() -> None:
    service = AiLiteService()

    answer = service.answer("как начать")

    assert "/commands" in answer
    assert "/feedback <текст>" in answer


def test_ai_answers_olegovirus_canon_question() -> None:
    service = AiLiteService()

    answer = service.answer("что такое Олеговирус и KHM?")

    assert "локальной базе канона" in answer
    assert "Олеговирус" in answer
    assert "KHM" in answer
    assert "не равный реальному Олегу" in answer
    assert "Google Doc" in answer


def test_ai_answers_ltl_and_teaology_question() -> None:
    service = AiLiteService()

    answer = service.answer("что такое LTL-паразит и Чайная религия?")

    assert "LTL-паразит" in answer
    assert "СНЧ" in answer
    assert "Чайная религия" in answer
    assert len(answer) < 2500


def test_ai_short_mode_compacts_canon_answer() -> None:
    service = AiLiteService()

    answer = service.answer("чай", mode="short")

    assert "Коротко по канону" in answer
    assert "Включите /long" in answer
    assert "Источник: Google Doc" not in answer
    assert len(answer) < 500


def test_ai_warns_about_prohibited_canon_topics() -> None:
    service = AiLiteService()

    answer = service.answer("можно ли писать про внешность реальных людей в каноне?")

    assert "канон запрещает" in answer
    assert "внешность реальных людей" in answer
    assert "медицинские диагнозы" in answer


def test_ai_answers_canon_sources_question() -> None:
    service = AiLiteService()

    answer = service.answer("какие есть источники канона и документ?")

    assert "Основной источник" in answer
    assert "docs.google.com" in answer
    assert "Рейтинг LTRS" in answer


def test_ai_answers_glossary_post_question() -> None:
    service = AiLiteService()

    answer = service.answer("что значит антиген POST в глоссарии?")

    assert "Глоссарий канона" in answer
    assert "Антиген POST" in answer
    assert "прилипание к чужим текстам" in answer


def test_ai_answers_high_canon_articles_question() -> None:
    service = AiLiteService()

    answer = service.answer("какие статьи высокого канона?")

    assert "Статьи высокого канона" in answer
    assert "Чайная религия (Teaology)" in answer
    assert "Философия конфет" in answer
    assert "Рейтинг участников чата по системе LTRS" in answer
    assert "https://t.me/lucasteamgroup/30105" in answer
