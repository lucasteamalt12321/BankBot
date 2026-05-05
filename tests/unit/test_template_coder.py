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


def test_data_tables_are_complete() -> None:
    service = TemplateCoderService()

    assert service.data_stats() == {
        "templates": 10,
        "single_values": 10,
        "pair_values": 100,
        "triple_values": 500,
    }


def test_help_text_lists_commands_and_templates() -> None:
    service = TemplateCoderService()

    text = service.help_text()

    assert "Диалоговый кодер шаблонов." in text
    assert "/coder - открыть этот модуль и сбросить состояние" in text
    assert "/reset - сбросить текущую последовательность" in text
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
    assert "/help" in text
    assert "Скоро буду" in text


def test_extract_bot_mentioned_coder_commands() -> None:
    assert _extract_bot_mentioned_command("/coder@lt_lo_game_bot", "lt_lo_game_bot") == "/coder"
    assert _extract_bot_mentioned_command("/help@lt_lo_game_bot", "@lt_lo_game_bot") == "/help"
    assert _extract_bot_mentioned_command("/reset@lt_lo_game_bot", "lt_lo_game_bot") == "/reset"
    assert _extract_bot_mentioned_command("/coder@other_bot", "lt_lo_game_bot") == ""


def test_first_step_lists_all_second_templates() -> None:
    service = TemplateCoderService()

    response, state = service.process("Скоро буду", CoderState())

    assert state.step == 1
    assert state.a_code == 8
    assert state.b_code is None
    assert state.updated_at is not None
    assert "Вы написали «Скоро буду», что значит «Скоро буду / Иду»." in response
    assert "Варианты для второго шаблона (любой из 10):" in response
    assert "ОК → «Буду через 5 минут»" in response
    assert "Нет → «Не скоро буду (долго)»" in response


def test_second_step_lists_only_allowed_third_templates() -> None:
    service = TemplateCoderService()

    response, state = service.process("ОК", CoderState(step=1, a_code=8))

    assert state.step == 2
    assert state.a_code == 8
    assert state.b_code == 1
    assert state.updated_at is not None
    assert "Вы написали «Скоро буду → ОК», что значит «Буду через 5 минут»." in response
    assert "Теперь вы можете прислать третий шаблон из списка: ОК, Да, Спасибо, Великолепно, Нет." in response
    assert "ОК → «Буду через 5 минут»" in response
    assert "Да → «Буду через 10 минут»" in response
    assert "Спасибо еще раз →" not in response


def test_third_step_finishes_and_resets() -> None:
    service = TemplateCoderService()

    response, state = service.process("Да", CoderState(step=2, a_code=8, b_code=1))

    assert state == CoderState()
    assert "Вы написали «Скоро буду → ОК → Да», что значит «Буду через 10 минут»." in response
    assert "Конец последовательности." in response


def test_third_step_rejects_disallowed_template() -> None:
    service = TemplateCoderService()

    response, state = service.process(
        "Спасибо еще раз",
        CoderState(step=2, a_code=8, b_code=1),
    )

    assert state.step == 2
    assert state.a_code == 8
    assert state.b_code == 1
    assert "На третьем шаге разрешены только: ОК, Да, Спасибо, Великолепно, Нет." in response
    assert "Вы написали «Спасибо еще раз»." in response


def test_repeated_first_template_restarts_sequence() -> None:
    service = TemplateCoderService()

    response, state = service.process("Спасибо", CoderState(step=1, a_code=3))

    assert state.step == 1
    assert state.a_code == 3
    assert response.startswith("Начинаю новую последовательность. Вы написали «Спасибо»")


def test_active_state_expires_after_30_minutes() -> None:
    service = TemplateCoderService()
    now = datetime.now(UTC)
    fresh_state = CoderState(step=1, a_code=8, updated_at=now - timedelta(minutes=29))
    expired_state = CoderState(step=1, a_code=8, updated_at=now - timedelta(minutes=31))

    assert service.is_expired(fresh_state, now=now) is False
    assert service.is_expired(expired_state, now=now) is True


def test_empty_state_never_expires() -> None:
    service = TemplateCoderService()

    assert service.is_expired(CoderState()) is False


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
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(chat_data={})

    handled = await dialog.handle_text(update, context)

    assert handled is True
    message.reply_text.assert_awaited_once()
    assert context.chat_data[dialog.state_key].step == 1
    assert context.chat_data[dialog.state_key].a_code == 3


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
    update = SimpleNamespace(effective_message=message)
    context = SimpleNamespace(
        chat_data={
            dialog.state_key: CoderState(
                step=2,
                a_code=8,
                b_code=1,
                updated_at=datetime.now(UTC) - timedelta(minutes=31),
            )
        }
    )

    handled = await dialog.handle_text(update, context)

    assert handled is True
    assert context.chat_data[dialog.state_key].step == 1
    assert context.chat_data[dialog.state_key].a_code == 1


async def test_dialog_reset_command_clears_state() -> None:
    dialog = TemplateCoderDialog()
    message = SimpleNamespace(reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(chat_data={dialog.state_key: CoderState(step=1, a_code=8)})

    await dialog.reset_command(update, context)

    assert context.chat_data[dialog.state_key] == CoderState()
    message.reply_text.assert_awaited_once()
