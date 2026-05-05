"""
Message handler module.

Handles general message processing that doesn't match specific commands.
"""

from aiogram import Router, types
from aiogram.filters import StateFilter

router = Router()


@router.message(StateFilter(None))
async def handle_message(message: types.Message):
    """Handle general messages."""
    # TODO: Implement general message handling logic
    pass
