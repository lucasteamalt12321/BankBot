from bot.ai.service import AiLiteService, MAX_QUESTION_LENGTH
from bot.ai.knowledge_updater import (
    _extract_ranked_source_urls,
    load_dynamic_knowledge,
)
from bot.commands import ai_commands
from bot.response_modes import compact_reply_text, set_user_mode


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
    assert "Запрещены темы внешности" not in answer


def test_ai_prefers_specific_olegovirus_over_generic_canon_rules() -> None:
    service = AiLiteService()

    answer = service.answer("кто такой олеговирус?", mode="short")

    assert "Олеговирус — вымышленный" in answer
    assert "Канон запрещает" not in answer
    assert "Лука/LucasTeam" not in answer


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


def test_extract_ranked_sources_keeps_high_and_medium_only() -> None:
    text = """
    🔵 Высокий канон: https://t.me/lucasteamgd/705
    🟡 Средний канон: https://t.me/lucasteamgroup/123
    ⚪ Низкий канон: https://t.me/lucasteamgroup/999
    """

    sources = _extract_ranked_source_urls(text)

    assert ("https://t.me/lucasteamgd/705", "Высокий") in sources
    assert ("https://t.me/lucasteamgroup/123", "Средний") in sources
    assert all(url != "https://t.me/lucasteamgroup/999" for url, _level in sources)


def test_ai_loads_runtime_knowledge_cache(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "ai_knowledge_cache.json"
    cache_path.write_text(
        """
        {
          "updated_at": "2026-05-18T00:00:00+00:00",
          "entries": [
            {
              "title": "runtime_test",
              "keywords": ["свежеканон"],
              "answer": "📖 Свежеканон из runtime-кэша для ИИ",
              "source": "https://t.me/lucasteamgd/1",
              "canon_level": "Высокий"
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr("bot.ai.service.load_dynamic_knowledge", lambda: load_dynamic_knowledge(cache_path))

    service = AiLiteService()
    answer = service.answer("что такое свежеканон?")

    assert "Свежеканон из runtime-кэша" in answer


async def test_ai_update_knowledge_command_requires_admin(monkeypatch) -> None:
    replies = []

    class AdminSystem:
        def is_admin(self, user_id):
            return False

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(ai_commands, "_reply_text_with_retry", fake_reply)

    await ai_commands.ai_update_knowledge_command(_FakeUpdate("/ai_update_knowledge"), None, AdminSystem())

    assert "только администратору" in replies[0]


def test_global_short_mode_compacts_long_bot_message() -> None:
    user_id = 123456
    set_user_mode(user_id, "short")
    long_text = "\n".join(f"Строка {index}: подробное описание раздела и команды" for index in range(30))

    compacted = compact_reply_text(long_text, user_id)

    assert len(compacted) < len(long_text)
    assert "/long — полный ответ" in compacted
    assert "Строка 29" not in compacted


def test_global_long_mode_keeps_full_bot_message() -> None:
    user_id = 654321
    set_user_mode(user_id, "long")
    long_text = "\n".join(f"Строка {index}: подробное описание раздела и команды" for index in range(30))

    compacted = compact_reply_text(long_text, user_id)

    assert compacted == long_text


class _FakeUser:
    id = 101
    username = "tester"
    first_name = "Test"


class _FakeChat:
    id = -100
    type = "supergroup"


class _FakeMessage:
    def __init__(self, text: str, reply_to_message=None, message_id: int = 10):
        self.text = text
        self.reply_to_message = reply_to_message
        self.message_id = message_id
        self.chat = _FakeChat()


class _FakeUpdate:
    def __init__(self, text: str, reply_to_message=None):
        self.message = _FakeMessage(text, reply_to_message=reply_to_message)
        self.effective_user = _FakeUser()
        self.effective_chat = _FakeChat()


async def test_ai_negative_feedback_asks_for_improvement(monkeypatch) -> None:
    ai_commands._pending_ai_improvements.clear()
    saved_entries = []
    replies = []

    def fake_save(entry):
        saved_entries.append(entry)

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(ai_commands, "_save_ai_feedback", fake_save)
    monkeypatch.setattr(ai_commands, "_reply_text_with_retry", fake_reply)

    ai_message = _FakeMessage("🤖 Коротко по канону:\n• Олеговирус — вымышленный", message_id=77)
    handled = await ai_commands.handle_ai_feedback_reply(_FakeUpdate("-", ai_message), None)

    assert handled is True
    assert saved_entries[0]["type"] == "ai_feedback_negative"
    assert saved_entries[0]["ai_answer"].startswith("🤖")
    assert "Что улучшить" in replies[0]


async def test_ai_improvement_text_is_saved_after_minus(monkeypatch) -> None:
    ai_commands._pending_ai_improvements.clear()
    saved_entries = []
    replies = []

    def fake_save(entry):
        saved_entries.append(entry)

    async def fake_reply(update, text, **kwargs):
        replies.append(text)

    monkeypatch.setattr(ai_commands, "_save_ai_feedback", fake_save)
    monkeypatch.setattr(ai_commands, "_reply_text_with_retry", fake_reply)

    ai_message = _FakeMessage("🤖 Коротко по канону:\n• Олеговирус — вымышленный", message_id=78)
    await ai_commands.handle_ai_feedback_reply(_FakeUpdate("-", ai_message), None)
    handled = await ai_commands.handle_ai_feedback_reply(_FakeUpdate("Добавить примеры KHM и POST"), None)

    assert handled is True
    assert saved_entries[-1]["type"] == "ai_feedback_improvement"
    assert saved_entries[-1]["text"] == "Добавить примеры KHM и POST"
    assert "сохранено" in replies[-1]
