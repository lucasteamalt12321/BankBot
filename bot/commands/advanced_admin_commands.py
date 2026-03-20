# advanced_admin_commands.py - Advanced administrative commands for Telegram bot
"""
Advanced Admin Command Handlers for Telegram Bot Advanced Features
Implements Requirements 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 10.1, 10.4, 10.5
"""

import os
import sys
from typing import Optional
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db
from core.services.admin_service import AdminService
from core.services.admin_stats_service import AdminStatsService
from core.services.broadcast_service import BroadcastService
from core.services.shop_service import ShopService
from core.services.user_service import UserService
from decimal import Decimal
import decimal
import structlog

logger = structlog.get_logger()

router = Router()


@router.message(Command("parsing_stats"))
async def parsing_stats_command(message: Message, db=next(get_db())):
    """Command /parsing_stats - Display parsing statistics with time-based filtering."""
    user = message.from_user
    logger.info("Parsing stats command requested", user_id=user.id)
    
    admin_service = AdminService(db)
    
    if not admin_service.is_admin(user.id):
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "Эта команда доступна только администраторам.",
            parse_mode='HTML'
        )
        logger.warning("Unauthorized parsing stats access attempt", user_id=user.id)
        return
    
    timeframe = "24h"
    if message.get_args():
        requested_timeframe = message.get_args().lower().strip()
        if requested_timeframe in ["24h", "7d", "30d"]:
            timeframe = requested_timeframe
    
    try:
        admin_stats_service = AdminStatsService(db)
        parsing_stats = await admin_stats_service.get_parsing_stats(timeframe)
        
        if not parsing_stats:
            await message.answer(
                "❌ <b>Ошибка получения статистики</b>\n\n"
                "Не удалось получить статистику парсинга. "
                "Попробуйте позже или обратитесь к разработчику.",
                parse_mode='HTML'
            )
            return
        
        text = f"""📊 <b>Статистика парсинга</b>

⏰ <b>Период:</b> {parsing_stats.period_name}
📅 <b>С:</b> {parsing_stats.start_time[:19].replace('T', ' ')}
📅 <b>По:</b> {parsing_stats.end_time[:19].replace('T', ' ')}

📈 <b>Общая статистика:</b>
   • Всего транзакций: {parsing_stats.total_transactions}
   • Успешных парсингов: {parsing_stats.successful_parses}
   • Неудачных парсингов: {parsing_stats.failed_parses}
   • Процент успеха: {parsing_stats.success_rate}%
   • Общая сумма конвертирована: {parsing_stats.total_amount_converted:.2f} монет

🤖 <b>Активные боты:</b> {parsing_stats.active_bots} из {parsing_stats.total_configured_bots}

"""
        
        if parsing_stats.bot_statistics:
            text += "🔍 <b>Статистика по ботам:</b>\n"
            for bot_stat in parsing_stats.bot_statistics:
                text += f"""
<b>{bot_stat['bot_name']}</b>
   • Транзакций: {bot_stat['transaction_count']} ({bot_stat['percentage_of_total']}%)
   • Исходная сумма: {bot_stat['total_original_amount']:.2f}
   • Конвертировано: {bot_stat['total_converted_amount']:.2f}
   • Валюта: {bot_stat['currency_type']}
"""
        
        if parsing_stats.parsing_rules:
            text += "\n⚙️ <b>Правила парсинга:</b>\n"
            for rule in parsing_stats.parsing_rules:
                status = "✅" if rule['is_active'] else "❌"
                text += f"   {status} {rule['bot_name']} (x{rule['multiplier']})\n"
        
        text += f"\n💡 <b>Совет:</b> Используйте /parsing_stats [24h|7d|30d] для разных периодов"
        
        await message.answer(text, parse_mode='HTML')
        logger.info(
            "Parsing stats displayed successfully",
            user_id=user.id,
            timeframe=timeframe,
            total_transactions=parsing_stats.total_transactions
        )
        
    except Exception as e:
        logger.error("Error in parsing stats command", error=str(e), user_id=user.id)
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при получении статистики парсинга. "
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode='HTML'
        )


@router.message(Command("broadcast"))
async def broadcast_command(message: Message, db=next(get_db())):
    """Command /broadcast - Broadcast message to all users with admin verification."""
    user = message.from_user
    logger.info("Broadcast command requested", user_id=user.id)
    
    admin_service = AdminService(db)
    
    if not admin_service.is_admin(user.id):
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "Эта команда доступна только администраторам.",
            parse_mode='HTML'
        )
        logger.warning("Unauthorized broadcast access attempt", user_id=user.id)
        return
    
    if not message.get_args():
        await message.answer(
            "❌ <b>Не указан текст сообщения</b>\n\n"
            "Использование: /broadcast <текст_сообщения>\n\n"
            "<b>Пример:</b>\n"
            "/broadcast Важное объявление для всех пользователей!",
            parse_mode='HTML'
        )
        return
    
    broadcast_message = message.get_args()
    
    if len(broadcast_message.strip()) == 0:
        await message.answer(
            "❌ <b>Пустое сообщение</b>\n\n"
            "Сообщение для рассылки не может быть пустым.",
            parse_mode='HTML'
        )
        return
    
    try:
        from aiogram import Bot
        bot = Bot.get_current()
        
        broadcast_service = BroadcastService(db, bot)
        admin_stats_service = AdminStatsService(db)
        
        await message.answer(
            f"📢 <b>Начинаю рассылку...</b>\n\n"
            f"<b>Сообщение:</b>\n{broadcast_message}\n\n"
            f"<b>Отправитель:</b> @{user.username or user.first_name}\n"
            f"⏳ Пожалуйста, подождите...",
            parse_mode='HTML'
        )
        
        result = await broadcast_service.broadcast_to_all(broadcast_message, user.id)
        
        if result:
            success_rate = (result.successful_sends / max(result.total_users, 1)) * 100
            
            text = f"""✅ <b>Рассылка завершена!</b>

📊 <b>Статистика доставки:</b>
   • Всего пользователей: {result.total_users}
   • Успешно доставлено: {result.successful_sends}
   • Ошибок доставки: {result.failed_sends}
   • Процент успеха: {success_rate:.1f}%

⏱️ <b>Время выполнения:</b> {result.execution_time:.2f} сек
📝 <b>Сообщение:</b> {broadcast_message[:100]}{'...' if len(broadcast_message) > 100 else ''}

👤 <b>Администратор:</b> @{user.username or user.first_name}"""
            
            if result.failed_sends > 0:
                text += f"\n\n⚠️ <b>Примечание:</b> {result.failed_sends} сообщений не доставлено из-за ошибок"
            
            await message.answer(text, parse_mode='HTML')
            logger.info(
                "Broadcast completed successfully",
                admin_id=user.id,
                total_users=result.total_users,
                successful_sends=result.successful_sends,
                failed_sends=result.failed_sends
            )
            
        else:
            await message.answer(
                "❌ <b>Ошибка рассылки</b>\n\n"
                "Не удалось выполнить рассылку. Возможные причины:\n"
                "• Ошибка подключения к базе данных\n"
                "• Проблемы с Telegram API\n"
                "• Системная ошибка\n\n"
                "Попробуйте позже или обратитесь к разработчику.",
                parse_mode='HTML'
            )
            logger.error("Broadcast failed", admin_id=user.id)
            
    except Exception as e:
        logger.error("Error in broadcast command", error=str(e), user_id=user.id)
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при выполнении рассылки. "
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode='HTML'
        )


@router.message(Command("user_stats"))
async def user_stats_command(message: Message, db=next(get_db())):
    """Command /user_stats - Display detailed user statistics with username lookup."""
    user = message.from_user
    logger.info("User stats command requested", user_id=user.id)
    
    admin_service = AdminService(db)
    
    if not admin_service.is_admin(user.id):
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "Эта команда доступна только администраторам.",
            parse_mode='HTML'
        )
        logger.warning("Unauthorized user stats access attempt", user_id=user.id)
        return
    
    if not message.get_args():
        await message.answer(
            "❌ <b>Не указан пользователь</b>\n\n"
            "Использование: /user_stats <@username>\n\n"
            "<b>Примеры:</b>\n"
            "• /user_stats @john_doe\n"
            "• /user_stats john_doe\n"
            "• /user_stats Иван",
            parse_mode='HTML'
        )
        return
    
    target_username = message.get_args().strip()
    
    try:
        admin_stats_service = AdminStatsService(db)
        user_stats = await admin_stats_service.get_user_stats(target_username)
        
        if not user_stats:
            await message.answer(
                f"❌ <b>Пользователь не найден</b>\n\n"
                f"Пользователь '{target_username}' не найден в системе.\n\n"
                f"💡 <b>Возможные причины:</b>\n"
                f"• Неверное имя пользователя\n"
                f"• Пользователь не зарегистрирован в боте\n"
                f"• Опечатка в имени\n\n"
                f"Попробуйте другое имя или проверьте правильность написания.",
                parse_mode='HTML'
            )
            logger.warning("User not found for stats", target_username=target_username, admin_id=user.id)
            return
        
        text = f"""👤 <b>Статистика пользователя</b>

🆔 <b>Основная информация:</b>
   • ID: {user_stats.user_id}
   • Имя: {user_stats.first_name or 'Не указано'}
   • Username: @{user_stats.username or 'Не указан'}
   • Дата регистрации: {user_stats.created_at[:19].replace('T', ' ')}
   • Последняя активность: {user_stats.last_activity[:19].replace('T', ' ')}

💰 <b>Финансовая информация:</b>
   • Текущий баланс: {user_stats.current_balance:.2f} монет
   • Всего заработано: {user_stats.total_earned:.2f} монет
   • Заработано парсингом: {user_stats.total_parsing_earnings:.2f} монет
   • Всего покупок: {user_stats.total_purchases}

🏆 <b>Статус и достижения:</b>
   • Администратор: {'✅ Да' if user_stats.is_admin else '❌ Нет'}
   • VIP статус: {'✅ Да' if user_stats.is_vip else '❌ Нет'}
   • Дневная серия: {user_stats.daily_streak} дней

"""
        
        if user_stats.active_subscriptions:
            text += "🎫 <b>Активные подписки:</b>\n"
            for subscription in user_stats.active_subscriptions:
                expires_text = ""
                if subscription['expires_at']:
                    expires_text = f" (до {subscription['expires_at'][:19].replace('T', ' ')})"
                text += f"   • {subscription['description']}{expires_text}\n"
            text += "\n"
        else:
            text += "🎫 <b>Активные подписки:</b> Нет\n\n"
        
        if user_stats.recent_purchases:
            text += "🛒 <b>Последние покупки:</b>\n"
            for purchase in user_stats.recent_purchases[:3]:
                purchase_date = purchase['purchased_at'][:10]
                status = "✅ Активна" if purchase['is_active'] else "❌ Неактивна"
                text += f"   • {purchase['item_name']} - {purchase['price_paid']} монет ({purchase_date}) - {status}\n"
            text += "\n"
        
        if user_stats.parsing_transaction_history:
            text += "📈 <b>История парсинга (последние 5):</b>\n"
            for transaction in user_stats.parsing_transaction_history[:5]:
                transaction_date = transaction['parsed_at'][:10]
                text += f"   • {transaction['source_bot']}: +{transaction['converted_amount']:.2f} монет ({transaction_date})\n"
            text += "\n"
        else:
            text += "📈 <b>История парсинга:</b> Нет транзакций\n\n"
        
        text += f"👨‍💼 <b>Запрос выполнен администратором:</b> @{user.username or user.first_name}"
        
        await message.answer(text, parse_mode='HTML')
        logger.info(
            "User stats displayed successfully",
            admin_id=user.id,
            target_username=target_username,
            target_user_id=user_stats.user_id,
            balance=user_stats.current_balance
        )
        
    except Exception as e:
        logger.error("Error in user stats command", error=str(e), user_id=user.id, target_username=target_username)
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при получении статистики пользователя. "
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode='HTML'
        )


@router.message(Command("add_item"))
async def add_item_command(message: Message, db=next(get_db())):
    """Command /add_item - Add new shop items dynamically with admin verification."""
    user = message.from_user
    logger.info("Add item command requested", user_id=user.id)
    
    admin_service = AdminService(db)
    
    if not admin_service.is_admin(user.id):
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "Эта команда доступна только администраторам.",
            parse_mode='HTML'
        )
        logger.warning("Unauthorized add item access attempt", user_id=user.id)
        return
    
    if not message.get_args():
        await message.answer(
            "❌ <b>Неверные параметры</b>\n\n"
            "<b>Использование:</b> /add_item &lt;название&gt; &lt;цена&gt; &lt;тип&gt;\n\n"
            "<b>Типы товаров:</b>\n"
            "• <code>sticker</code> - Безлимитные стикеры на 24 часа\n"
            "• <code>admin</code> - Товар с уведомлением администраторов\n"
            "• <code>mention_all</code> - Право на рассылку всем пользователям\n"
            "• <code>custom</code> - Кастомный товар\n\n"
            "<b>Примеры:</b>\n"
            "• /add_item \"Премиум стикеры\" 100 sticker\n"
            "• /add_item \"VIP статус\" 500 admin\n"
            "• /add_item \"Объявление\" 200 mention_all",
            parse_mode='HTML'
        )
        return
    
    try:
        args = message.get_args().split()
        
        if len(args) < 3:
            raise ValueError("Insufficient parameters")
        
        potential_type = args[-1].lower()
        valid_types = {"sticker", "admin", "mention_all", "custom"}
        
        if potential_type not in valid_types:
            raise ValueError(f"Invalid item type. Valid types: {', '.join(valid_types)}")
        
        item_type = potential_type
        
        if len(args) < 3:
            raise ValueError("Price not provided")
        
        try:
            price_str = args[-2]
            price = Decimal(price_str)
        except (ValueError, TypeError, decimal.InvalidOperation):
            raise ValueError("Invalid price format")
        
        if len(args) < 3:
            raise ValueError("Price not provided")
        
        price_index = len(args) - 2
        name_parts = args[:price_index]
        name = ' '.join(name_parts).strip('"\'')
        
        if not name:
            raise ValueError("Item name is empty")
        
        if price <= 0:
            raise ValueError("Price must be positive")
        
    except (ValueError, IndexError) as e:
        await message.answer(
            f"❌ <b>Ошибка в параметрах</b>\n\n"
            f"Проблема: {str(e)}\n\n"
            f"<b>Правильный формат:</b>\n"
            f"/add_item &lt;название&gt; &lt;цена&gt; &lt;тип&gt;\n\n"
            f"<b>Пример:</b>\n"
            f"/add_item \"Новый товар\" 150 sticker",
            parse_mode='HTML'
        )
        return
    
    try:
        shop_service = ShopService(db)
        result = await shop_service.add_item(name, int(price), item_type)
        
        if result["success"]:
            item = result["item"]
            type_descriptions = {
                "sticker": "🎨 Безлимитные стикеры на 24 часа",
                "admin": "👨‍💼 Товар с уведомлением администраторов",
                "mention_all": "📢 Право на рассылку всем пользователям",
                "custom": "⚙️ Кастомный товар"
            }
            
            text = f"""✅ <b>Товар успешно добавлен!</b>

🆔 <b>ID товара:</b> {item['id']}
📝 <b>Название:</b> {item['name']}
💰 <b>Цена:</b> {item['price']} монет
🏷️ <b>Тип:</b> {item['item_type']}
📋 <b>Описание:</b> {type_descriptions.get(item['item_type'], 'Товар')}
✅ <b>Статус:</b> {'Активен' if item['is_active'] else 'Неактивен'}

🛒 <b>Товар доступен для покупки!</b>
Пользователи могут приобрести его через команду /buy

👨‍💼 <b>Добавлено администратором:</b> @{user.username or user.first_name}"""
            
            await message.answer(text, parse_mode='HTML')
            logger.info(
                "Shop item added successfully",
                admin_id=user.id,
                item_id=item['id'],
                item_name=name,
                price=price,
                item_type=item_type
            )
            
        else:
            error_messages = {
                "INVALID_ITEM_TYPE": "❌ <b>Недопустимый тип товара</b>\n\nДопустимые типы: sticker, admin, mention_all, custom",
                "DUPLICATE_NAME": f"❌ <b>Товар уже существует</b>\n\nТовар с названием '{name}' уже есть в магазине. Выберите другое название.",
                "INVALID_PRICE": "❌ <b>Неверная цена</b>\n\nЦена должна быть больше нуля.",
                "CREATION_ERROR": "❌ <b>Ошибка создания</b>\n\nПроизошла ошибка при добавлении товара в базу данных."
            }
            
            error_code = result.get("error_code", "UNKNOWN_ERROR")
            error_message = error_messages.get(error_code, result["message"])
            
            await message.answer(error_message, parse_mode='HTML')
            logger.warning(
                "Failed to add shop item",
                admin_id=user.id,
                item_name=name,
                price=price,
                item_type=item_type,
                error_code=error_code,
                error_message=result["message"]
            )
            
    except Exception as e:
        logger.error("Error in add item command", error=str(e), user_id=user.id)
        await message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Произошла ошибка при добавлении товара. "
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode='HTML'
        )
