"""Regression tests for the error-logging path.

``send_telegram_message`` reports its own failures through ``log_error``, and
``log_error`` notifies the admin through ``send_telegram_message``. Without the
reentrancy guard that chain is infinite recursion with a real HTTP call per
iteration, which froze requests whenever Telegram was unreachable.
"""

from unittest.mock import patch

import api.index as m


def test_send_telegram_failure_does_not_recurse():
    """A failing Telegram call must not recurse through log_error -> notify_admin."""
    calls = []

    def boom(*_args, **_kwargs):
        calls.append(1)
        raise RuntimeError("telegram unreachable")

    with patch.object(m, "BOT_TOKEN", "test-token"), \
         patch.object(m, "ADMIN_TELEGRAM_ID", 42), \
         patch("requests.post", side_effect=boom):
        m.send_telegram_message(42, "привет")

    assert len(calls) < 10, f"error path recursed {len(calls)} times"


def test_nested_log_error_records_entry_without_ai_call():
    """A log_error triggered from inside log_error must not call AI or notify again."""
    with patch.object(m, "notify_admin") as notify:
        def reentrant(_module, _error_type, _message, _context=""):
            # This is what send_telegram_message does when Telegram is down.
            m.log_error("SEND_MSG", "error", "вложенная ошибка")
            return "rec"

        with patch.object(m, "_get_ai_recommendation", side_effect=reentrant) as ai:
            m.log_error("DB", "error", "внешняя ошибка")
            assert ai.call_count == 1
            assert notify.call_count == 1

    assert any(e["message"] == "вложенная ошибка" for e in m._ERROR_LOG)
    assert any(e["message"] == "внешняя ошибка" for e in m._ERROR_LOG)


def test_log_error_never_raises():
    """Even if the AI provider blows up, log_error still records the entry."""
    with patch.object(m, "_get_ai_recommendation", side_effect=RuntimeError("ai down")), \
         patch.object(m, "notify_admin"):
        m.log_error("AI", "error", "boom")
    assert any(e["message"] == "boom" for e in m._ERROR_LOG)


def test_info_errors_do_not_notify_admin():
    with patch.object(m, "_get_ai_recommendation", return_value="ok"), \
         patch.object(m, "notify_admin") as notify:
        m.log_error("DB", "info", "просто инфо")
        assert notify.call_count == 0
