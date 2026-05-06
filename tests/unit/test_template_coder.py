from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.bot import _extract_bot_mentioned_command
from bot.template_coder.dialog import TemplateCoderDialog
from bot.template_coder.service import CoderState, TemplateCoderService


def test_normalize_aliases() -> None:
    service = TemplateCoderService()

    assert service.normalize("спасибо нет") == 4
    assert service.normalize("Спасибо, нет") == 4
    assert service.normalize("я занят") == 9
    assert service.normalize("спасибо еще раз") == 6
    assert service.normalize("ОК") == 1


def test_data_tables_are_removed() -> None:
    service = TemplateCoderService()

    assert service.data_stats()["templates"] == 10
    assert service.data_stats()["pair_values"] == 0
    assert service.data_stats()["triple_values"] == 0


def test_help_text_lists_commands_and_templates() -> None:
    service = TemplateCoderService()

    text = service.help_text()

    assert "Диалоговый кодер шаблонов." in text
    assert "/coder - открыть этот модуль и сбросить состояние" in text
    assert "/reset - сбросить текущую последовательность" in text
    assert "/done - закончить и вывести финальную фразу" in text
    assert "4. \"Спасибо, нет\"" in text
    assert "10. Нет" in text


def test_start_text_resets_and_prompts_first_template() -> None:
    service = TemplateCoderService()

    text = service.start_text()

    assert "Состояние сброшено." in text
    assert "напишите первый шаблон" in text
    assert "1. ОК" in text


def test_welcome_hint_mentions_coder_commands() -> None:
    service = TemplateCoderService()

    text = service.welcome_hint_text()

    assert "Диалоговый кодер шаблонов" in text
    assert "/coder" in text
    assert "/reset" in text
    assert "/done" in text
    assert "/help" in text
    assert "Скоро буду" in text


def test_extract_bot_mentioned_coder_commands() -> None:
    assert _extract_bot_mentioned_command("/coder@lt_lo_game_bot", "lt_lo_game_bot") == "/coder"
    assert _extract_bot_mentioned_command("/help@lt_lo_game_bot", "@lt_lo_game_bot") == "/help"
    assert _extract_bot_mentioned_command("/reset@lt_lo_game_bot", "lt_lo_game_bot") == "/reset"
    assert _extract_bot_mentioned_command("/done@lt_lo_game_bot", "lt_lo_game_bot") == "/done"
    assert _extract_bot_mentioned_command("/coder@other_bot", "lt_lo_game_bot") == ""


def test_first_step_initializes_arrival_and_lists_all_templates() -> None:
    service = TemplateCoderService()

    response, state = service.process("Скоро буду", CoderState())

    assert state.steps == 1
    assert state.topic == "arrival"
    assert state.time_minutes == 5
    assert state.history == [8]
    assert state.updated_at is not None
    assert "Вы написали: «Скоро буду»" in response
    assert "Текущий смысл: «Буду через 5 минут»" in response
    assert response.count(" → «") == 10
    assert "ОК → «Буду через 5 минут»" in response
    assert "Нет → «Буду через 15 минут, но не спешу»" in response


def test_sequence_has_unlimited_parametric_steps() -> None:
    service = TemplateCoderService()
    state = CoderState()

    for text in ["Скоро буду", "ОК", "Спасибо", "Да", "Нет", "Скоро буду"]:
        _response, state = service.process(text, state)

    assert state.steps == 6
    assert state.history == [8, 1, 3, 2, 10, 8]
    assert state.topic == "arrival"
    assert state.time_minutes == 9


def test_arrival_specific_rules() -> None:
    service = TemplateCoderService()
    state = CoderState()

    _response, state = service.process("Скоро буду", state)
    _response, state = service.process("Да", state)
    assert service.render(state) == "Буду через 1 минуту, спешу"

    _response, state = service.process("Спасибо, нет", state)
    assert state.time_minutes == 21
    assert state.confidence == 0.8
    assert service.render(state).startswith("Возможно, буду через 21 минуту")


def test_thanks_rules_can_turn_into_refusal() -> None:
    service = TemplateCoderService()

    _response, state = service.process("Спасибо", CoderState())
    _response, state = service.process("Великолепно", state)
    assert state.topic == "thanks"
    assert state.politeness == 2
    assert service.render(state).startswith("Огромное спасибо")

    _response, state = service.process("Нет", state)
    assert state.topic == "refusal"
    assert service.render(state) == "Спасибо, нет, категорически"


def test_done_text_resets_in_dialog() -> None:
    service = TemplateCoderService()
    _response, state = service.process("Да", CoderState())

    assert service.done_text(state) == (
        "Готово! Смысл вашей последовательности: «Да, конечно». "
        "Чтобы начать новую, пришлите первый шаблон."
    )
    assert service.done_text(CoderState()).startswith("Последовательность пуста")


def test_active_state_expires_after_30_minutes() -> None:
    service = TemplateCoderService()
    now = datetime.now(UTC)
    fresh_state = CoderState(steps=1, history=[8], updated_at=now - timedelta(minutes=29))
    expired_state = CoderState(steps=1, history=[8], updated_at=now - timedelta(minutes=31))

    assert service.is_expired(fresh_state, now=now) is False
    assert service.is_expired(expired_state, now=now) is True


def test_empty_state_never_expires() -> None:
    service = TemplateCoderService()

    assert service.is_expired(CoderState()) is False


def test_saturation_warning_after_10_steps() -> None:
    service = TemplateCoderService()
    state = CoderState()

    response = ""
    for _ in range(10):
        response, state = service.process("ОК", state)

    assert state.steps == 10
    assert "Вы достигли максимальной глубины уточнений" in response
    assert "/done" in response


def test_dialog_import_smoke() -> None:
    dialog = TemplateCoderDialog()

    assert dialog.is_template_text("ОК") is True
    assert dialog.is_template_text("не шаблон") is False


def test_bot_import_exposes_template_coder_attribute() -> None:
    from bot.bot import TelegramBot

    assert hasattr(TelegramBot, "welcome_command")
    assert hasattr(TelegramBot, "handle_mentioned_commands")


async def test_dialog_handles_template_text_and_stores_state() -> None:
    dialog = TemplateCoderDialog()
    message = SimpleNamespace(text="Спасибо", reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=1))
    context = SimpleNamespace(chat_data={})

    handled = await dialog.handle_text(update, context)

    assert handled is True
    message.reply_text.assert_awaited_once()
    assert context.chat_data[dialog.state_key].steps == 1
    assert context.chat_data[dialog.state_key].topic == "thanks"


async def test_dialog_ignores_non_template_without_active_state() -> None:
    dialog = TemplateCoderDialog()
    message = SimpleNamespace(text="обычный текст", reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(chat_data={})

    handled = await dialog.handle_text(update, context)

    assert handled is False
    message.reply_text.assert_not_awaited()


async def test_dialog_resets_expired_state_before_new_template() -> None:
    dialog = TemplateCoderDialog()
    message = SimpleNamespace(text="ОК", reply_text=AsyncMock())
    update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=1))
    context = SimpleNamespace(
        chat_data={
            dialog.state_key: CoderState(
                topic="arrival",
                time_minutes=5,
                steps=2,
                history=[8, 1],
                updated_at=datetime.now(UTC) - timedelta(minutes=31),
            )
        }
    )

    handled = await dialog.handle_text(update, context)

    assert handled is True
    assert context.chat_data[dialog.state_key].steps == 1
    assert context.chat_data[dialog.state_key].history == [1]


async def test_dialog_reset_command_clears_state() -> None:
    dialog = TemplateCoderDialog()
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(chat_data={dialog.state_key: CoderState(steps=1, history=[8])})

    await dialog.reset_command(update, context)

    assert context.chat_data[dialog.state_key] == CoderState()
    message.reply_text.assert_awaited_once()


async def test_dialog_done_command_outputs_final_and_clears_state() -> None:
    dialog = TemplateCoderDialog()
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(
        chat_data={dialog.state_key: CoderState(topic="arrival", time_minutes=5, steps=1, history=[8])}
    )

    await dialog.done_command(update, context)

    assert context.chat_data[dialog.state_key] == CoderState()
    message.reply_text.assert_awaited_once()
    assert "Буду через 5 минут" in message.reply_text.await_args.args[0]
