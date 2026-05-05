"""Balance commands — aiogram router."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="balance")


@router.message(Command("balance"))
async def balance_cmd(message: Message) -> None:
    """Show user balance."""
    await message.answer("💰 Команда /balance (aiogram)")


@router.message(Command("history"))
async def history_cmd(message: Message) -> None:
    """Show transaction history."""
    await message.answer("📋 Команда /history (aiogram)")
