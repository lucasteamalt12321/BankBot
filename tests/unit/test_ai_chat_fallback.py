"""Tests for api.index._ai_chat provider fallback.

Regression: gpt-oss-фильтр критериев применялся ко ВСЕМ провайдерам и молча
пропускал Gemini (primary никогда не вызывался); _groq_active_model читался/писался
и для Gemini.
"""

from unittest.mock import MagicMock, patch

import pytest

import api.index as idx


def _resp(status_code: int, content: str = "", tool_calls: bool = False) -> MagicMock:
    """Build a fake requests.Response with OpenAI-style JSON body."""
    r = MagicMock()
    r.status_code = status_code
    r.text = "mock-body"
    msg: dict = {"message": {"content": content}}
    if tool_calls:
        msg["message"]["tool_calls"] = [{"function": {"name": "x", "arguments": "{}"}}]
    r.json.return_value = {"choices": [msg]}
    return r


@pytest.fixture
def ai_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g_key")
    monkeypatch.setenv("GROQ_API_KEY", "groq_key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    monkeypatch.delenv("GROQ_API_KEY_3", raising=False)
    monkeypatch.setitem(idx._groq_active_model, "name", None)


PAYLOAD = {
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 10,
    "temperature": 0.3,
}


def test_gemini_primary_is_used_when_ok(ai_env):
    """Gemini должен вызываться первым и возвращаться, а не отфильтровываться."""
    gem = _resp(200, "gem answer")
    with patch("api.index.requests.post", return_value=gem) as m:
        out = idx._ai_chat(dict(PAYLOAD))
    assert out is gem
    assert m.call_count == 1
    url = m.call_args[0][0]
    assert "generativelanguage.googleapis.com" in url
    body = m.call_args[1]["json"]
    assert body["model"] == "gemini-2.5-flash"
    assert idx._groq_active_model["name"] is None


def test_gemini_empty_content_falls_back_to_groq(ai_env):
    """200 с пустым content от Gemini → fallback на Groq (gpt-oss)."""
    gem = _resp(200, "")
    groq = _resp(200, "groq answer")
    with patch("api.index.requests.post", side_effect=[gem, groq]) as m:
        out = idx._ai_chat(dict(PAYLOAD))
    assert out is groq
    assert m.call_count == 2
    groq_url = m.call_args_list[1][0][0]
    assert "api.groq.com" in groq_url
    assert idx._groq_active_model["name"] == "openai/gpt-oss-120b"


def test_gemini_error_falls_back_to_groq(ai_env):
    """Ошибка Gemini (500) → Groq."""
    gem = _resp(500, "server err")
    groq = _resp(200, "groq answer")
    with patch("api.index.requests.post", side_effect=[gem, groq]) as m:
        out = idx._ai_chat(dict(PAYLOAD))
    assert out is groq
    assert m.call_count == 2


def test_gemini_skipped_without_key(ai_env, monkeypatch):
    """Без GEMINI_API_KEY → сразу Groq (порядок провайдеров корректный)."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    groq = _resp(200, "groq answer")
    with patch("api.index.requests.post", return_value=groq) as m:
        out = idx._ai_chat(dict(PAYLOAD))
    assert out is groq
    assert "api.groq.com" in m.call_args[0][0]


def test_groq_active_model_not_applied_to_gemini(ai_env):
    """Активная Groq-модель НЕ должна подмешиваться в запрос Gemini."""
    idx._groq_active_model["name"] = "openai/gpt-oss-120b"
    gem = _resp(404, "nf")
    groq = _resp(200, "groq answer")
    with patch("api.index.requests.post", side_effect=[gem, groq]) as m:
        out = idx._ai_chat(dict(PAYLOAD))
    assert out is groq
    gem_body = m.call_args_list[0][1]["json"]
    assert gem_body["model"] == "gemini-2.5-flash"
    groq_body = m.call_args_list[1][1]["json"]
    assert groq_body["model"] == "openai/gpt-oss-120b"