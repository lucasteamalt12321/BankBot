"""
Callback handler module.

Handles callback queries from inline keyboards.
"""

from aiogram import Router, types

router = Router()


@router.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    """Handle callback queries."""
    # TODO: Implement callback handling logic
    await callback.answer()
