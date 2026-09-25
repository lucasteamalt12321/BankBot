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
        reply, intent = m._family_chat_dialog("system", "Аня: мама забрала телефон", None)
    assert call.call_args.kwargs["max_tokens"] == 400
    assert len(reply) <= 900
    assert intent == "emotion"
    assert "intent_type" not in reply
