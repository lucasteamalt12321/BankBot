"""User commands module."""

from aiogram import Router, types
from aiogram.filters import Command
from core.services.user_service import UserService
from core.services.transaction_service import TransactionService

router = Router()


@router.message(Command("profile"))
async def profile_command(message: types.Message, user_service: UserService):
    """Show user profile."""
    user = user_service.get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("👤 Пользователь не найден")
        return
    
    text = f"""👤 <b>Профиль пользователя</b>

🆔 <b>ID:</b> {user.id}
👤 <b>Имя:</b> {user.first_name or 'Не указано'}
📝 <b>Username:</b> @{user.username or 'Не указан'}
📅 <b>Дата регистрации:</b> {user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else 'Неизвестно'}
:last_activity: <b>Последняя активность:</b> {user.last_activity.strftime('%Y-%m-%d %H:%M:%S') if user.last_activity else 'Неизвестно'}

🏆 <b>Статус:</b>
   • Дневная серия: {user.daily_streak} дней
   • VIP статус: {'✅ Да' if user.is_vip else '❌ Нет'}

💰 <b>Финансовая информация:</b>
   • Текущий баланс: {user.balance} очков
   • Всего заработано: {user.total_earned} очков
   • Всего покупок: {user.total_purchases}"""

    await message.answer(text, parse_mode='HTML')


@router.message(Command("balance"))
async def balance_command(message: types.Message, user_service: UserService):
    """Show user balance."""
    user = user_service.get_user_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer("💰 Пользователь не найден")
        return
    
    await message.answer(f"💰 Ваш баланс: {user.balance} очков")
