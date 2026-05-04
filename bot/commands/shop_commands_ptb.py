"""Shop commands for python-telegram-bot."""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

logger = structlog.get_logger()


async def shop_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    auto_registration_middleware,
    get_db,
):
    """Команда /shop - просмотр магазина."""
    await auto_registration_middleware.process_message(update, context)

    user = update.effective_user
    logger.info(f"Shop command from user {user.id}")

    try:
        db = next(get_db())

        from core.handlers.shop_handler import ShopHandler

        shop_handler = ShopHandler(db)
        shop_display = shop_handler.display_shop(user.id)

        await update.message.reply_text(shop_display)

    except Exception as e:
        logger.error(f"Error in shop command: {e}")
        fallback_text = """🛒 МАГАЗИН

❌ Произошла ошибка при загрузке магазина. Попробуйте позже.

Для связи с администратором используйте /buy_contact"""
        await update.message.reply_text(fallback_text)


async def buy_contact_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    admin_system,
    get_db,
):
    """Команда /buy_contact для покупки товаров."""
    from utils.admin.admin_middleware import auto_registration_middleware

    await auto_registration_middleware.process_message(update, context)

    user = update.effective_user

    try:
        admin_user = admin_system.get_user_by_username(user.username or str(user.id))
        if not admin_user:
            success = admin_system.register_user(user.id, user.username, user.first_name)
            if not success:
                await update.message.reply_text("❌ Ошибка регистрации пользователя")
                return

            admin_user = admin_system.get_user_by_username(user.username or str(user.id))
            if not admin_user:
                await update.message.reply_text("❌ Не удалось найти пользователя")
                return

        current_balance = admin_user["balance"]
        required_amount = 10

        if current_balance < required_amount:
            await update.message.reply_text(
                f"❌ Недостаточно очков для покупки. "
                f"Требуется: {required_amount} очков, "
                f"у вас: {int(current_balance)} очков",
            )
            return

        new_balance = admin_system.update_balance(user.id, -required_amount)
        if new_balance is None:
            await update.message.reply_text("❌ Не удалось обновить баланс")
            return

        admin_system.add_transaction(user.id, -required_amount, "buy")

        await update.message.reply_text("Вы купили контакт. Администратор свяжется с вами.")

        try:
            conn = admin_system.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT telegram_id FROM users WHERE is_admin = TRUE")
            admin_ids = [row["telegram_id"] for row in cursor.fetchall()]
            conn.close()

            username_display = f"@{user.username}" if user.username else f"#{user.id}"
            admin_message = (
                f"Пользователь {username_display} купил контакт. "
                f"Его баланс: {int(new_balance)} очков"
            )

            for admin_id in admin_ids:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=admin_message)
                except Exception as e:
                    logger.warning(
                        f"Failed to send notification to admin {admin_id}: {e}",
                    )

            logger.info(
                f"User {user.id} bought contact, notified {len(admin_ids)} admins",
            )

        except Exception as e:
            logger.error(f"Error notifying admins about purchase: {e}")

    except Exception as e:
        logger.error(f"Error in buy_contact command: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при покупке. "
            "Попробуйте позже или обратитесь к администратору.",
        )


async def buy_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    auto_registration_middleware,
    get_db,
):
    """Команда /buy - покупка товара."""
    from utils.admin.admin_middleware import auto_registration_middleware

    await auto_registration_middleware.process_message(update, context)

    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "❌ Укажите номер товара!\n\n"
            "Использование: /buy <номер_товара>\n"
            "Пример: /buy 1\n\n"
            "Посмотрите доступные товары: /shop",
        )
        return

    try:
        item_number = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный номер товара!\n\n"
            "Номер товара должен быть числом (1, 2, 3...)\n"
            "Посмотрите доступные товары: /shop",
        )
        return

    db = next(get_db())
    try:
        from core.managers.shop_manager import ShopManager

        shop_manager = ShopManager(db)
        result = await shop_manager.process_purchase(user.id, item_number)

        if result.success:
            text = f"""✅ <b>Покупка успешна!</b>

{result.message}

💰 Новый баланс: {result.new_balance} монет
🛒 ID покупки: {result.purchase_id}

Товар активирован и готов к использованию!"""

            try:
                from utils.monitoring.notification_system import NotificationSystem

                notification_system = NotificationSystem(db, bot=context.bot)
                shop_items = shop_manager.get_shop_items()
                if shop_items and 1 <= item_number <= len(shop_items):
                    item = shop_items[item_number - 1]
                    await notification_system.send_purchase_notification(
                        user.id,
                        item.name,
                        int(item.price),
                        int(result.new_balance),
                    )
            except Exception as notification_error:
                logger.warning(
                    f"Failed to send purchase notification: {notification_error}",
                )

            await update.message.reply_text(text, parse_mode="HTML")
            logger.info(
                f"Purchase successful: user {user.id}, item {item_number}, purchase {result.purchase_id}",
            )

        else:
            error_text = f"❌ {result.message}"

            if result.error_code == "INSUFFICIENT_BALANCE":
                error_text += "\n\n💡 Заработайте больше монет, участвуя в играх!"
            elif result.error_code == "ITEM_NOT_FOUND":
                error_text += "\n\n💡 Посмотрите доступные товары: /shop"
            elif result.error_code == "USER_NOT_FOUND":
                error_text += "\n\n💡 Используйте /start для регистрации"

            await update.message.reply_text(error_text)
            logger.warning(
                f"Purchase failed: user {user.id}, item {item_number}, error: {result.error_code}",
            )

    except Exception as e:
        logger.error(f"Error in buy command: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке покупки.\n"
            "Попробуйте позже или обратитесь к администратору.",
        )
    finally:
        db.close()


async def _handle_purchase_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    item_number: int,
    auto_registration_middleware,
    get_db,
):
    """Обработчик команд покупки товаров."""
    await auto_registration_middleware.process_message(update, context)

    user = update.effective_user
    logger.info(f"Purchase command /buy_{item_number} from user {user.id}")

    db = next(get_db())
    try:
        from core.managers.shop_manager import ShopManager

        shop_manager = ShopManager(db)
        result = await shop_manager.process_purchase(user.id, item_number)

        if result.success:
            text = f"""✅ <b>Покупка успешна!</b>

{result.message}

💰 Новый баланс: {result.new_balance} монет
🛒 ID покупки: {result.purchase_id}

Товар активирован и готов к использованию!"""

            try:
                from utils.monitoring.notification_system import NotificationSystem

                notification_system = NotificationSystem(db, bot=context.bot)
                shop_items = shop_manager.get_shop_items()
                if shop_items and 1 <= item_number <= len(shop_items):
                    item = shop_items[item_number - 1]
                    await notification_system.send_purchase_notification(
                        user.id,
                        item.name,
                        int(item.price),
                        int(result.new_balance),
                    )
            except Exception as notification_error:
                logger.warning(
                    f"Failed to send purchase notification: {notification_error}",
                )

            await update.message.reply_text(text, parse_mode="HTML")
            logger.info(
                f"Purchase successful: user {user.id}, item {item_number}, purchase {result.purchase_id}",
            )

        else:
            error_text = f"❌ {result.message}"

            if result.error_code == "INSUFFICIENT_BALANCE":
                error_text += "\n\n💡 Заработайте больше монет, участвуя в играх!"
            elif result.error_code == "ITEM_NOT_FOUND":
                error_text += "\n\n💡 Посмотрите доступные товары: /shop"
            elif result.error_code == "USER_NOT_FOUND":
                error_text += "\n\n💡 Используйте /start для регистрации"

            await update.message.reply_text(error_text)
            logger.warning(
                f"Purchase failed: user {user.id}, item {item_number}, error: {result.error_code}",
            )

    except Exception as e:
        logger.error(f"Error in buy_{item_number} command: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке покупки. "
            "Попробуйте позже или обратитесь к администратору.",
        )
    finally:
        db.close()


async def inventory_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    get_db,
):
    """Команда /inventory - инвентарь."""
    from core.systems.shop_system import EnhancedShopSystem

    user = update.effective_user

    db = next(get_db())
    try:
        shop = EnhancedShopSystem(db)
        inventory = shop.get_user_inventory(user.id)

        if not inventory:
            await update.message.reply_text("Vash inventar pust")
            return

        text = "[BAG] <b>Ваш инвентарь</b>\n\n"

        active_items = [i for i in inventory if i["is_active"]]
        expired_items = [i for i in inventory if not i["is_active"]]

        if active_items:
            text += "[YES] <b>Активные товары:</b>\n"
            for item in active_items:
                text += f"• {item['item_name']}\n"
                if item["expires_at"]:
                    text += f"  ⏰ Истекает: {item['expires_at'].strftime('%d.%m.%Y %H:%M')}\n"
                text += f"  🛒 Куплен: {item['purchased_at'].strftime('%d.%m.%Y')}\n\n"

        if expired_items:
            text += "[NO] <b>Неактивные товары:</b>\n"
            for item in expired_items[:5]:
                text += f"• {item['item_name']} (истек)\n"

        await update.message.reply_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in inventory command: {e}")
        await update.message.reply_text(f"Oshibka: {str(e)}")
    finally:
        db.close()
