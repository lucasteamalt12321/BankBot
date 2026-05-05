"""System commands module."""

from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command("start"))
async def start_command(message: types.Message):
    """Start command."""
    await message.answer("🤖 Добро пожаловать в LucasTeam Bot!")


@router.message(Command("help"))
async def help_command(message: types.Message):
    """Help command."""
    await message.answer("❓ Справка")
