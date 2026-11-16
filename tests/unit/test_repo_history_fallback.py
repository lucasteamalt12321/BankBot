"""Регресс фикса «ИИ недоступен» в /repo_history (2026-11-14).

Graceful-fallback: при отказе/пустом ответе ИИ страница отдаёт детерминированную
сводку по коммитам (200, ai=False), а не 502. OpenRouter повторяет 429 с паузой.
"""

import os
from unittest.mock import patch

import pytest

from api import repo_history as rh
from api.index import _AI_RATE_LIMITS, _ai_chat, app


@pytest.fixture(autouse=True)
def _reset_caches():
    _AI_RATE_LIMITS.clear()
    rh._CONTEXT_CACHE.clear()
    rh._SUMMARY_CACHE.clear()
    yield
    _AI_RATE_LIMITS.clear()
    rh._CONTEXT_CACHE.clear()
    rh._SUMMARY_CACHE.clear()


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


def _commit(msg="feat: add thing", sha="abc1234", date="2026-11-01T00:00:00Z"):
    return {"sha": sha, "author": "a", "date": date, "message": msg}


def _ai_ok(text="Сводка готова."):
    return _Resp(200, {"choices": [{"message": {"content": text}}]})


def test_fallback_groups_by_prefix():
    commits = [
        _commit("feat: new module"),
        _commit("fix(core): race"),
        _commit("random message"),
    ]
    out = rh.build_fallback_summary(commits, "последние 7 дн.", False)
    assert "Новые функции (1)" in out
    assert "Исправления (1)" in out
    assert "Прочее / обслуживание (1)" in out
    assert "недоступен" in out


def test_fallback_brief_and_truncated():
    out = rh.build_fallback_summary([_commit()], "p", True, brief=True)
    assert "1 коммитов" in out
    full = rh.build_fallback_summary([_commit()], "p", True)
    assert "обрезан" in full


def test_analyze_empty_ai_reply_falls_back():
    with (
        patch("api.index._ai_chat", return_value=_ai_ok("   ")),
        patch("api.repo_history.fetch_commits", return_value=([_commit()], False)),
        patch("api.repo_history.fetch_memory_bank", return_value={}),
        patch("api.index._check_db_rate", return_value=False),
        patch("api.index._check_ai_rate", return_value=False),
    ):
        r = app.test_client().post(
            "/api/repo_history/analyze",
            json={"url": "https://github.com/u/r", "days": 7},
        )
    assert r.status_code == 200
    d = r.get_json()
    assert d["ai"] is False
    assert d["summary"]


def test_openrouter_retries_429():
    env = {
        "GEMINI_API_KEY": "",
        "GROQ_API_KEY": "",
        "OPENROUTER_API_KEY": "k",
        "OPENROUTER_MODEL": "m/free",
    }
    calls = []

    def _post(url, **kw):
        calls.append(url)
        return _Resp(429) if len(calls) == 1 else _ai_ok()

    with (
        patch.dict(os.environ, env, clear=False),
        patch("api.index._groq_api_keys", return_value=[]),
        patch("api.index.requests.post", side_effect=_post),
        patch("api.index.time.sleep"),
    ):
        resp = _ai_chat({"messages": [{"role": "user", "content": "hi"}]}, timeout=1.0)
    assert resp is not None and resp.status_code == 200
    assert len(calls) == 2


def test_analyze_caches_successful_summary():
    with (
        patch("api.index._ai_chat", return_value=_ai_ok("Готово.")) as ai,
        patch("api.index._get_ai_recommendation", return_value="—"),
        patch("api.repo_history.fetch_commits", return_value=([_commit()], False)),
        patch("api.repo_history.fetch_memory_bank", return_value={}),
        patch("api.index._check_db_rate", return_value=False),
        patch("api.index._check_ai_rate", return_value=False),
    ):
        c = app.test_client()
        body = {"url": "https://github.com/u/cached", "days": 7}
        r1 = c.post("/api/repo_history/analyze", json=body)
        r2 = c.post("/api/repo_history/analyze", json=body)
    assert r1.status_code == 200 and r1.get_json()["ai"] is True
    assert r2.status_code == 200 and r2.get_json()["ai"] is True
    assert r2.get_json()["summary"] == "Готово."
    assert ai.call_count == 1


def test_analyze_failure_not_cached():
    with (
        patch("api.index._ai_chat", return_value=_Resp(429)) as ai,
        patch("api.index._get_ai_recommendation", return_value="—"),
        patch("api.repo_history.fetch_commits", return_value=([_commit()], False)),
        patch("api.repo_history.fetch_memory_bank", return_value={}),
        patch("api.index._check_db_rate", return_value=False),
        patch("api.index._check_ai_rate", return_value=False),
    ):
        c = app.test_client()
        body = {"url": "https://github.com/u/uncached", "days": 7}
        r1 = c.post("/api/repo_history/analyze", json=body)
        r2 = c.post("/api/repo_history/analyze", json=body)
    assert r1.get_json()["ai"] is False and r2.get_json()["ai"] is False
    assert ai.call_count == 2