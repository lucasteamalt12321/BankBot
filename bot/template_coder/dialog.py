"""Telegram adapter for the dialog template coder service."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.template_coder.service import CoderState, TemplateCoderService


class TemplateCoderDialog:
    """Stores per-chat state in PTB ``chat_data`` and sends responses."""

    state_key = "template_coder_state"

    def __init__(self, service: TemplateCoderService | None = None) -> None:
        self.service = service or TemplateCoderService()

    def has_active_state(self, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Return true if the current chat has a partially entered sequence."""
        state = self._get_state(context)
        return state.step > 0

    def is_template_text(self, text: str | None) -> bool:
        """Return true if text is a known template alias."""
        return self.service.is_template_text(text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show coder help."""
        await update.message.reply_text(self.service.help_text())

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start coder mode and reset current coder state."""
        self._set_state(context, self.service.empty_state())
        await update.message.reply_text(self.service.start_text())

    def reset_state(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Reset coder state without sending a message."""
        self._set_state(context, self.service.empty_state())

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Reset coder state for a chat."""
        self._set_state(context, self.service.empty_state())
        await update.message.reply_text(self.service.start_text())

    async def handle_text(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> bool:
        """Process text if it belongs to the coder dialog.

        Returns:
            ``True`` if the message was answered by this module.
        """
        message = update.effective_message
        if message is None or message.text is None:
            return False

        state = self._get_state(context)
        if self.service.is_expired(state):
            state = self.service.empty_state()
            self._set_state(context, state)
        should_answer = state.step > 0 or self.is_template_text(message.text)
        if not should_answer:
            return False

        response, new_state = self.service.process(message.text, state)
        self._set_state(context, new_state)
        await message.reply_text(response)
        return True

    def _get_state(self, context: ContextTypes.DEFAULT_TYPE) -> CoderState:
        raw = context.chat_data.get(self.state_key)
        if isinstance(raw, CoderState):
            return raw
        if isinstance(raw, dict):
            if raw.get("updated_at") and isinstance(raw["updated_at"], str):
                raw = {**raw, "updated_at": None}
            return CoderState(**raw)
        return self.service.empty_state()

    def _set_state(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        state: CoderState,
    ) -> None:
        context.chat_data[self.state_key] = state
