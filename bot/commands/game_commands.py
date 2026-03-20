"""Game commands module."""

from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command("games"))
async def games_command(message: types.Message):
    """Show available games."""
    await message.answer("🎮 Доступные игры")
