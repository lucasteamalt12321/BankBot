"""Unit tests for bridge_bot.loop_guard module."""

import pytest

from bridge_bot.loop_guard import BOT_MARK, add_bot_mark, has_bot_mark


class TestBotMark:
    """Tests for the [BOT] loop prevention mark."""

    def test_bot_mark_constant(self):
        """Verify BOT_MARK constant is correctly defined."""
        assert BOT_MARK == "[BOT]"

    def test_has_bot_mark_positive(self):
        """Text containing [BOT] mark should return True."""
        assert has_bot_mark("Hello [BOT]") is True
        assert has_bot_mark("[BOT] Forwarded message") is True
        assert has_bot_mark("Some text with [BOT] in middle") is True

    def test_has_bot_mark_negative(self):
        """Text without [BOT] mark should return False."""
        assert has_bot_mark("Hello world") is False
        assert has_bot_mark("") is False
        assert has_bot_mark("[BOTCAUTION]") is False
        assert has_bot_mark("[BOTA]") is False
        assert has_bot_mark("BOT in text") is False

    def test_has_bot_mark_case_sensitive(self):
        """[BOT] detection should be case-sensitive."""
        assert has_bot_mark("[bot]") is False
        assert has_bot_mark("[Bot]") is False
        assert has_bot_mark("[BOT]") is True

    def test_add_bot_mark(self):
        """add_bot_mark should append [BOT] to text."""
        result = add_bot_mark("Hello world")
        assert result == "Hello world [BOT]"

    def test_add_bot_mark_empty(self):
        """add_bot_mark should handle empty string."""
        result = add_bot_mark("")
        assert result == " [BOT]"

    def test_add_bot_mark_already_has_mark(self):
        """add_bot_mark should not duplicate existing mark."""
        result = add_bot_mark("Hello [BOT]")
        assert result == "Hello [BOT] [BOT]"

    def test_roundtrip(self):
        """Adding mark then checking should detect it."""
        text = "Original message"
        marked = add_bot_mark(text)
        assert has_bot_mark(marked) is True
        assert marked == "Original message [BOT]"

    def test_unicode_handling(self):
        """Non-ASCII text should be handled correctly."""
        text = "Привет мир"
        marked = add_bot_mark(text)
        assert marked == "Привет мир [BOT]"
        assert has_bot_mark(marked) is True
