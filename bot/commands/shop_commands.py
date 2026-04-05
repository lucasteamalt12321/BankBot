"""Shop commands module."""

from aiogram import Router, types
from aiogram.filters import Command
from core.services.shop_service import ShopService

router = Router()


@router.message(Command("shop"))
async def shop_command(message: types.Message, shop_service: ShopService):
    """Show shop."""
    categories = shop_service.get_all_categories()

    if not categories:
        await message.answer("🛒 Магазин пуст")
        return

    text = "🛒 <b>Магазин товаров</b>\n\n"

    for category in categories:
        text += f"📂 <b>{category.name}</b>\n"
        if category.description:
            text += f"   {category.description}\n"
        text += "\n"

    text += "Используйте /buy [id товара] для покупки"

    await message.answer(text, parse_mode='HTML')


@router.message(Command("inventory"))
async def inventory_command(message: types.Message, shop_service: ShopService):
    """Show user inventory."""
    user = shop_service.user_repo.get_by_telegram_id(message.from_user.id)

    if not user:
        await message.answer("🎒 Пользователь не найден")
        return

    purchases = shop_service.get_user_purchases(user.id)

    if not purchases:
        await message.answer("🎒 Ваш инвентарь пуст")
        return

    text = "🎒 <b>Ваш инвентарь</b>\n\n"

    for purchase in purchases:
        item = purchase.item
        if item:
            status = "✅ Активен" if purchase.is_active else "❌ Неактивен"
            text += f"• {item.name} - {item.price} очков ({status})\n"

    await message.answer(text, parse_mode='HTML')
