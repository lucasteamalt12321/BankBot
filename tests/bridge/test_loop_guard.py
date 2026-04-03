"""Tests for bridge_bot.loop_guard module."""

from __future__ import annotations


from bridge_bot.loop_guard import add_bot_mark, has_bot_mark, BOT_MARK


class TestBotMark:
    """Tests for [BOT] mark functions."""

    def test_bot_mark_constant(self):
        """Test BOT_MARK constant value."""
        assert BOT_MARK == "[BOT]"

    def test_has_bot_mark_true(self):
        """Test detection of [BOT] mark."""
        assert has_bot_mark("Hello [BOT]") is True
        assert has_bot_mark("[BOT] Hello") is True
        assert has_bot_mark("Hello [BOT] World") is True
        assert has_bot_mark("[BOT]") is True

    def test_has_bot_mark_false(self):
        """Test absence of [BOT] mark."""
        assert has_bot_mark("Hello World") is False
        assert has_bot_mark("BOT in text") is False
        assert has_bot_mark("bot") is False
        assert has_bot_mark("") is False

    def test_has_bot_mark_case_sensitive(self):
        """Test that has_bot_mark is case sensitive."""
        assert has_bot_mark("[bot]") is False
        assert has_bot_mark("[BOT]") is True
        assert has_bot_mark("[Bot]") is False

    def test_add_bot_mark(self):
        """Test adding [BOT] mark to text."""
        result = add_bot_mark("Hello World")
        assert result == "Hello World [BOT]"

    def test_add_bot_mark_empty(self):
        """Test adding mark to empty string."""
        result = add_bot_mark("")
        assert result == " [BOT]"

    def test_add_bot_mark_already_has(self):
        """Test adding mark when it already exists."""
        result = add_bot_mark("Hello [BOT]")
        assert result == "Hello [BOT] [BOT]"

    def test_combined_flow(self):
        """Test full flow: add mark then check."""
        text = "Test message"
        marked = add_bot_mark(text)
        assert marked == "Test message [BOT]"
        assert has_bot_mark(marked) is True
