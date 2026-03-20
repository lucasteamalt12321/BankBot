# admin_commands.py - Административные команды для Telegram бота
import logging
from aiogram import Router, types
from aiogram.filters import Command
from core.services.admin_service import AdminService
from core.services.user_service import UserService
from core.services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("admin"))
async def admin_panel_command(message: types.Message, admin_service: AdminService, user_service: UserService):
    """Команда /admin - панель администратора."""
    user = user_service.get_user_by_telegram_id(message.from_user.id)
    
    if not user or not admin_service.is_admin(user.telegram_id):
        await message.answer("🔒 У вас нет прав администратора для выполнения этой команды.")
        return
    
    users_count = admin_service.get_users_count()
    
    text = f"""
🔧 <b>Панель администратора</b>

👋 Добро пожаловать, {message.from_user.first_name}!

📊 <b>Статистика:</b>
   • Всего пользователей: {users_count}

🛠️ <b>Доступные команды:</b>
   • /add_points @username [число] - начислить очки
   • /add_admin @username - добавить администратора
   • /admin - показать эту панель

💡 <b>Примеры использования:</b>
   • /add_points @john_doe 100
   • /add_admin @new_admin

⚠️ Будьте осторожны с административными командами!
    """
    
    await message.answer(text, parse_mode='HTML')
    logger.info(f"Admin panel accessed by user {message.from_user.id} (@{message.from_user.username})")


@router.message(Command("add_points"))
async def add_points_command(message: types.Message, admin_service: AdminService, transaction_service: TransactionService):
    """Команда /add_points - начисление очков пользователю."""
    user = message.from_user
    
    if not admin_service.is_admin(user.id):
        await message.answer("🔒 У вас нет прав администратора для выполнения этой команды.")
        return
    
    if not message.get_args() or len(message.get_args().split()) < 2:
        await message.answer(
            "❌ <b>Неверный формат команды</b>\n\n"
            "Используйте: /add_points @username [количество]\n\n"
            "<b>Примеры:</b>\n"
            "• /add_points @john_doe 100\n"
            "• /add_points user123 50",
            parse_mode='HTML'
        )
        return
    
    args = message.get_args().split()
    username = args[0]
    
    try:
        amount = int(args[1])
        if amount <= 0:
            await message.answer("❌ Количество очков должно быть положительным числом")
            return
    except ValueError:
        await message.answer("❌ Неверный формат количества очков")
        return
    
    try:
        # Находим пользователя
        target_user = admin_service.get_user_by_username(username)
        if not target_user:
            await message.answer(f"❌ Пользователь {username} не найден")
            return
        
        # Начисляем очки через сервис транзакций
        updated_user = await transaction_service.add_points(
            user_id=target_user.telegram_id,
            amount=amount,
            reason=f"Admin addition by {user.username or user.first_name}"
        )
        
        if not updated_user:
            await message.answer("❌ Не удалось обновить баланс пользователя")
            return
        
        text = f"""
✅ <b>Очки успешно начислены!</b>

👤 Пользователь: @{target_user.username or target_user.telegram_id}
💰 Начислено: {amount} очков
💳 Новый баланс: {updated_user.balance} очков
📝 ID транзакции: {updated_user.total_earned}

Администратор: @{user.username or user.first_name}
        """
        
        await message.answer(text, parse_mode='HTML')
        logger.info(f"Admin {user.id} added {amount} points to user {target_user.telegram_id}")
        
    except Exception as e:
        logger.error(f"Error in add_points command: {e}")
        await message.answer(
            "❌ Произошла ошибка при начислении очков. "
            "Попробуйте позже или обратитесь к разработчику."
        )


@router.message(Command("add_admin"))
async def add_admin_command(message: types.Message, admin_service: AdminService):
    """Команда /add_admin - назначение администратора."""
    user = message.from_user
    
    if not admin_service.is_admin(user.id):
        await message.answer("🔒 У вас нет прав администратора для выполнения этой команды.")
        return
    
    if not message.get_args():
        await message.answer(
            "❌ <b>Неверный формат команды</b>\n\n"
            "Используйте: /add_admin @username\n\n"
            "<b>Примеры:</b>\n"
            "• /add_admin @john_doe\n"
            "• /add_admin user123",
            parse_mode='HTML'
        )
        return
    
    username = message.get_args().strip()
    
    try:
        # Находим пользователя
        target_user = admin_service.get_user_by_username(username)
        if not target_user:
            await message.answer(f"❌ Пользователь {username} не найден")
            return
        
        # Проверяем, не является ли пользователь уже администратором
        if admin_service.is_admin(target_user.telegram_id):
            await message.answer(
                f"ℹ️ Пользователь @{target_user.username or target_user.telegram_id} "
                f"уже является администратором"
            )
            return
        
        # Назначаем администратором
        success = admin_service.set_admin_status(target_user.telegram_id, True)
        if not success:
            await message.answer("❌ Не удалось назначить пользователя администратором")
            return
        
        text = f"""
✅ <b>Администратор назначен!</b>

👤 Пользователь: @{target_user.username or target_user.telegram_id}
🔧 Статус: Администратор
👑 Назначен: @{user.username or user.first_name}

Теперь пользователь имеет доступ к административным командам.
        """
        
        await message.answer(text, parse_mode='HTML')
        logger.info(f"Admin {user.id} granted admin rights to user {target_user.telegram_id}")
        
    except Exception as e:
        logger.error(f"Error in add_admin command: {e}")
        await message.answer(
            "❌ Произошла ошибка при назначении администратора. "
            "Попробуйте позже или обратитесь к разработчику."
        )
