from bot.ai.service import AiLiteService, MAX_QUESTION_LENGTH


def test_ai_help_explains_free_local_mode() -> None:
    service = AiLiteService()

    text = service.help_text()

    assert "бесплатный локальный помощник" in text
    assert "/ai" in text
    assert "/ask" in text
    assert "без платных API" in text


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


def test_ai_rejects_too_long_question() -> None:
    service = AiLiteService()

    answer = service.answer("а" * (MAX_QUESTION_LENGTH + 1))

    assert "Вопрос слишком длинный" in answer


def test_ai_fallback_suggests_commands() -> None:
    service = AiLiteService()

    answer = service.answer("как начать")

    assert "/commands" in answer
    assert "/feedback <текст>" in answer
