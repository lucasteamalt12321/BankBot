"""Tests for the family mediator: short chat replies and no false crisis advice."""

from unittest.mock import patch

import api.index as m


def test_system_prompt_forbids_false_emergency_advice():
    prompt = m._family_build_system_prompt("Семья", ["Аня", "Боря"], 2, "—")
    lowered = prompt.lower()
    assert "звоните 112" in lowered, "the prompt must name the false-advice pattern explicitly"
    assert "бытовая" in lowered
    # The rule must be conditional on a real danger signal, not a blanket referral.
    assert "только" in lowered and "опасност" in lowered


def test_system_prompt_requires_short_replies():
    prompt = m._family_build_system_prompt("Семья", ["Аня"], 1, "—")
    assert "100 слов" in prompt
    assert "2–4 предложения" in prompt


def test_tidy_reply_truncates_runaway_output():
    text = "Разговор идёт. " + "Очень длинное рассуждение медиатора. " * 100
    out = m._family_tidy_reply(text)
    assert len(out) <= 900
    assert out.endswith((".", "!", "?"))


def test_tidy_reply_keeps_short_text_untouched():
    out = m._family_tidy_reply("Я слышу тебя.\n\n\n\n  Что для тебя важнее?")
    assert out == "Я слышу тебя.\n\n Что для тебя важнее?"


def test_chat_dialog_is_capped_and_strips_intent_json():
    long_reply = "Совет. " * 300 + '\n{"intent_type": "emotion"}'
    with patch.object(m, "call_ai_api", return_value=long_reply) as call:
        reply, intent, needs = m._family_chat_dialog("system", "Аня: мама забрала телефон", None)
    assert call.call_args.kwargs["max_tokens"] == 400
    assert len(reply) <= 900
    assert intent == "emotion"
    assert needs == []
    assert "intent_type" not in reply


def test_chat_dialog_extracts_structured_needs():
    ai_reply = "Похоже, тебе важно быть услышанным.\n" '{"intent_type": "emotion", "needs": ["быть услышанным"]}'
    with patch.object(m, "call_ai_api", return_value=ai_reply):
        reply, intent, needs = m._family_chat_dialog("system", "Аня: мама не слушает меня", None)
    assert intent == "emotion"
    assert needs == ["быть услышанным"]
    assert "intent_type" not in reply


def test_clean_needs_filters_injection_from_model_output():
    needs = m._family_clean_needs({"needs": ["хорошо", "быть услышанным", 123, "придуманная моделью потребность",
                                             " ", "длинная потребность" * 30]})
    assert "хорошо" not in needs  # too short
    assert "придуманная моделью потребность" in needs
    assert all(len(n) <= 200 for n in needs)


def test_pop_json_block_leaves_plain_reply_untouched():
    text, obj = m._family_pop_json_block("Просто ответ без json.")
    assert text == "Просто ответ без json."
    assert obj is None


def test_validate_name_and_password_limits():
    try:
        m._family_validate_name("А" * 101)
        raise AssertionError("expected ValueError for long name")
    except (ValueError, TypeError):
        pass
    try:
        m._family_validate_password("#" * 73)
        raise AssertionError("expected ValueError for long password")
    except (ValueError, TypeError):
        pass
