"""Единые подсказки «добавьте свой API-ключ ИИ» при ошибках ИИ.

Проверяем, что:
* хелпер `core/ai_errors` даёт единый текст со ссылкой на профиль;
* строковые контракты `call_ai_api` (отказ определяется по префиксу «❌»)
  не ломаются;
* ключевые модули (AI-чат, code explainer, md2pdf, repo history, бот)
  отдают пользователю подсказку с ключом;
* JS-хелпер внедряется на все страницы портала.
"""

from unittest.mock import patch

import api.index as idx
from core.ai_errors import (
    AI_KEY_PATH,
    ai_error,
    ai_error_payload,
    ai_key_hint,
    ai_key_js,
    ai_key_url,
    site_url,
)
from core.theme import inject_theme

PROFILE_MARK = "/account#ai-key"


# ── Хелпер ────────────────────────────────────────────────────────────────


def test_ai_error_contains_reason_and_profile_link():
    text = ai_error("ИИ недоступен")

    assert "ИИ недоступен" in text
    assert "свой API-ключ" in text
    assert ai_key_url() in text
    assert PROFILE_MARK in text


def test_ai_error_keeps_legacy_prefix_for_callers():
    # call_ai_api и его вызывающие определяют отказ по префиксу «❌».
    text = ai_error("Ошибка ИИ: 429", prefix="❌")

    assert text.startswith("❌")
    assert ai_key_url() in text


def test_ai_error_without_hint_and_payload_shape():
    assert "свой API-ключ" not in ai_error("ИИ недоступен", with_hint=False)

    payload = ai_error_payload("ИИ вернул пустой ответ")
    assert set(payload) == {"error"}
    assert "ИИ вернул пустой ответ" in payload["error"]
    assert ai_key_url() in payload["error"]


def test_ai_key_url_uses_site_url_env(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://example.test/")
    assert site_url() == "https://example.test"
    assert ai_key_url() == "https://example.test" + AI_KEY_PATH
    assert ai_key_url(absolute=False) == AI_KEY_PATH


def test_ai_key_js_defines_helpers():
    js = ai_key_js()

    assert "LTHubAI" in js
    assert "hintHtml" in js
    assert "hintMd" in js
    assert ai_key_url() in js


def test_inject_theme_adds_hint_script_once():
    html = inject_theme("<html><body><p>ok</p></body></html>")
    assert "app-ai-key-hint" in html

    twice = inject_theme(html)
    assert twice.count("app-ai-key-hint") == 1


# ── Веб-модули ────────────────────────────────────────────────────────────


def test_call_ai_api_failure_returns_hint():
    with patch.object(idx, "_ai_chat", return_value=None), patch.object(
        idx, "_groq_api_keys", return_value=[]
    ):
        answer = idx.call_ai_api("привет")

    assert answer.startswith("❌")
    assert ai_key_url() in answer


def test_pc_ai_chat_failure_reply_contains_hint():
    with patch.object(idx, "_request_user_ai_config", return_value=None), patch.object(
        idx, "_ai_chat", return_value=None
    ), patch.dict(idx.os.environ, {}, clear=False):
        result = idx._pc_ai_chat(
            "42",
            "olegov",
            [{"role": "user", "content": "привет"}],
            [],
            None,
        )

    assert result["reply"].startswith("❌")
    assert ai_key_url() in result["reply"]


def test_repo_history_page_embeds_hint_helper():
    from api import repo_history as rh

    html = rh.page_html()

    assert "LTHubAI.hint(" in html
    assert "app-ai-key-hint" in html


def test_bot_ai_lite_fallback_offers_own_key():
    from bot.ai.service import AiLiteService

    service = AiLiteService()
    answer = service.answer("что ты умеешь вообще")

    assert ai_key_url() in answer


def test_dnd_ai_master_error_text_offers_own_key():
    from core.systems import dnd_ai_master

    source = dnd_ai_master.__file__
    with open(source, encoding="utf-8") as fh:
        content = fh.read()

    assert "ai_error(" in content


def test_dnd_uses_personal_ai_key_first():
    from unittest.mock import Mock

    from api import dnd_runtime

    cfg = {"provider": "gemini", "api_key": "sk-test", "model": "gemini-2.5-flash"}
    resp = Mock(status_code=200)
    resp.json.return_value = {"choices": [{"message": {"content": "ответ мастера"}}]}

    with patch("api.index._request_user_ai_config", return_value=cfg), patch(
        "api.index._ai_chat_with_user_key", return_value=resp
    ):
        assert dnd_runtime._call_ai_with_user_key("привет", 100) == "ответ мастера"

    with patch("api.index._request_user_ai_config", return_value=None):
        assert dnd_runtime._call_ai_with_user_key("привет", 100) is None
