"""Единые сообщения об ошибках ИИ + подсказка «добавьте свой API-ключ».

Зарегистрированный пользователь LTHub может сохранить свой ключ нейросети
в профиле (``/account`` → «🔑 Мой AI-ключ»). Такой ключ используется
приоритетно (см. ``_ai_chat`` в ``api/index.py``), а при отказе ИИ
пользователю показывается подсказка с прямой ссылкой на этот блок.

Модуль лёгкий (только stdlib) и импортируется и из ``api/``, и из ``bot/``,
поэтому тексты ошибок ИИ везде собираются в одном месте: добавить новый
провайдер или поменять адрес профиля — достаточно поправить этот файл.
"""

from __future__ import annotations

import os

#: Куда ведёт подсказка «добавьте свой ключ» (якорь блока в /account).
AI_KEY_PATH = "/account#ai-key"

#: Публичный адрес LTHub по умолчанию (канонический прод-домен).
DEFAULT_SITE_URL = "https://lthub.vercel.app"

#: Ключи env, которыми можно переопределить адрес сайта.
SITE_URL_ENV_VARS = ("SITE_URL", "PUBLIC_URL", "LTHUB_SITE_URL")


def site_url() -> str:
    """Публичный адрес LTHub без слэша на конце."""

    for name in SITE_URL_ENV_VARS:
        value = (os.getenv(name) or "").strip()
        if value:
            return value.rstrip("/")
    return DEFAULT_SITE_URL


def ai_key_url(*, absolute: bool = True) -> str:
    """Ссылка на блок «Мой AI-ключ» в профиле."""

    base = site_url() if absolute else ""
    return f"{base}{AI_KEY_PATH}"


def ai_key_hint(*, absolute: bool = True) -> str:
    """Строка-подсказка: можно подключить свой ключ, вот ссылка."""

    return (
        "🔑 Можно подключить свой API-ключ ИИ — тогда запросы пойдут через него: "
        f"{ai_key_url(absolute=absolute)}"
    )


def ai_error(
    reason: str,
    *,
    absolute: bool = True,
    with_hint: bool = True,
    prefix: str = "⚠️",
) -> str:
    """Единый текст ошибки ИИ.

    ``reason`` — короткая причина («ИИ недоступен», «ИИ вернул пустой ответ»).
    К тексту добавляется подсказка про личный ключ и ссылка на профиль.

    ``prefix`` — начало сообщения. Для строк, где отказ определяется по
    префиксу ``"❌"`` (legacy-контракт ``call_ai_api`` и др.), передавайте
    ``prefix="❌"``, иначе вызывающий код примет ошибку за ответ ИИ.
    """

    text = f"{prefix} {reason}" if prefix else reason
    if with_hint:
        text += f"\n{ai_key_hint(absolute=absolute)}"
    return text


def ai_error_payload(reason: str, *, absolute: bool = True) -> dict:
    """JSON-ответ API: ``{"error": <текст с подсказкой про ключ>}``."""

    return {"error": ai_error(reason, absolute=absolute)}


#: JS-хелпер, который внедряется на все страницы портала (через inject_theme).
#: Даёт ``LTHubAI.hint(msg)`` (текст) и ``LTHubAI.hintHtml(msg)`` (с ссылкой).
AI_KEY_JS = """<script id="app-ai-key-hint">
(function () {
  var KEY_URL = '__AI_KEY_URL__';
  window.LTHubAI = window.LTHubAI || {};
  window.LTHubAI.keyUrl = KEY_URL;
  window.LTHubAI.hint = function (msg) {
    return (msg ? msg + ' ' : '') + '🔑 Можно подключить свой API-ключ ИИ: ' + KEY_URL;
  };
  window.LTHubAI.hintMd = function (msg) {
    return (msg ? msg + ' ' : '') + '🔑 [Добавить свой API-ключ ИИ](' + KEY_URL + ')';
  };
  window.LTHubAI.hintHtml = function (msg) {
    var safe = String(msg == null ? '' : msg)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return safe + ' <a href="' + KEY_URL + '" target="_blank" rel="noopener">🔑 Добавить свой API-ключ ИИ</a>';
  };
})();
</script>"""


def ai_key_js() -> str:
    """JS-хелпер подсказки про ключ с подставленным адресом профиля."""

    return AI_KEY_JS.replace("__AI_KEY_URL__", ai_key_url(absolute=True))
