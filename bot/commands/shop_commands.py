"""Shop commands module (python-telegram-bot 20.x)."""

from telegram import Update
from telegram.ext import ContextTypes

from database.database import get_db
from utils.admin.admin_middleware import auto_registration_middleware
from core.handlers.shop_handler import ShopHandler
from bot.middleware.dependency_injection import build_services


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /shop - просмотр магазина."""
    await auto_registration_middleware.process_message(update, context)

    db = next(get_db())
    try:
        handler = ShopHandler(db)
        text = handler.display_shop(update.effective_user.id)
        await update.message.reply_text(text)
    finally:
        db.close()


async def buy_contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /buy_contact для покупки контакта."""
    await auto_registration_middleware.process_message(update, context)

    user = update.effective_user

    with build_services() as svc:
        admin_user = svc.admin_service.get_user_by_username(user.username or str(user.id))
        if not admin_user:
            success = svc.admin_service.register_user(user.id, user.username, user.first_name)
            if not success:
                await update.message.reply_text("❌ Ошибка регистрации пользователя")
                return

            admin_user = svc.admin_service.get_user_by_username(user.username or str(user.id))
            if not admin_user:
                await update.message.reply_text("❌ Не удалось найти пользователя")
                return

        current_balance = admin_user["balance"]
        required_amount = 10

        if current_balance < required_amount:
            await update.message.reply_text(
                f"❌ Недостаточно очков для покупки. "
                f"Требуется: {required_amount} очков, "
                f"у вас: {int(current_balance)} очков"
            )
            return

        new_balance = svc.admin_service.update_balance(user.id, -required_amount)
        if new_balance is None:
            await update.message.reply_text("❌ Не удалось обновить баланс")
            return

        svc.admin_service.add_transaction(user.id, -required_amount, "buy")

        await update.message.reply_text("Вы купили контакт. Администратор свяжется с вами.")


async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /buy - покупка товара."""
    await auto_registration_middleware.process_message(update, context)

    if not context.args:
        await update.message.reply_text(
            "❌ Укажите номер товара!\n\nИспользование: /buy <номер_товара>"
        )
        return

    try:
        item_number = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный номер товара!\n\nНомер товара должен быть числом."
        )
        return

    await update.message.reply_text(f"✅ Покупка товара #{item_number} оформлена.")


async def _handle_purchase(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    item_number: int,
    auto_registration_middleware,
    get_db,
):
    """Обработчик команд покупки товаров по номеру."""
    await auto_registration_middleware.process_message(update, context)
    await update.message.reply_text(f"✅ Покупка товара #{item_number} оформлена.")


async def inventory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /inventory - инвентарь пользователя."""
    await update.message.reply_text("🎒 Ваш инвентарь пуст")
