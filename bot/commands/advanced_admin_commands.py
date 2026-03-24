# advanced_admin_commands.py - Advanced administrative commands for python-telegram-bot 20.x
"""
Advanced Admin Command Handlers for Telegram Bot.
Implements Requirements 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 10.1, 10.4, 10.5
"""

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from bot.middleware.dependency_injection import build_services

logger = structlog.get_logger()


class AdvancedAdminCommands:
    """Расширенные административные команды для PTB 20.x."""

    async def parsing_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /parsing_stats — статистика парсинга с фильтрацией по времени."""
        user = update.effective_user
        logger.info("Parsing stats command requested", user_id=user.id)

        with build_services() as svc:
            if not svc.admin_service.is_admin(user.id):
                await update.message.reply_text(
                    "❌ <b>Доступ запрещен</b>\n\nЭта команда доступна только администраторам.",
                    parse_mode="HTML",
                )
                return

            timeframe = "24h"
            if context.args:
                requested = context.args[0].lower().strip()
                if requested in ("24h", "7d", "30d"):
                    timeframe = requested

            try:
                from core.services.admin_stats_service import AdminStatsService
                admin_stats_service = AdminStatsService(svc.user_repo)
                parsing_stats = await admin_stats_service.get_parsing_stats(timeframe)

                if not parsing_stats:
                    await update.message.reply_text(
                        "❌ <b>Ошибка получения статистики</b>\n\nПопробуйте позже.",
                        parse_mode="HTML",
                    )
                    return

                text = (
                    f"📊 <b>Статистика парсинга</b>\n\n"
                    f"⏰ <b>Период:</b> {parsing_stats.period_name}\n"
                    f"📅 <b>С:</b> {parsing_stats.start_time[:19].replace('T', ' ')}\n"
                    f"📅 <b>По:</b> {parsing_stats.end_time[:19].replace('T', ' ')}\n\n"
                    f"📈 <b>Общая статистика:</b>\n"
                    f"   • Всего транзакций: {parsing_stats.total_transactions}\n"
                    f"   • Успешных парсингов: {parsing_stats.successful_parses}\n"
                    f"   • Неудачных парсингов: {parsing_stats.failed_parses}\n"
                    f"   • Процент успеха: {parsing_stats.success_rate}%\n"
                    f"   • Конвертировано: {parsing_stats.total_amount_converted:.2f} монет\n\n"
                    f"🤖 <b>Активные боты:</b> {parsing_stats.active_bots} из {parsing_stats.total_configured_bots}\n"
                )

                if parsing_stats.bot_statistics:
                    text += "\n🔍 <b>Статистика по ботам:</b>\n"
                    for bot_stat in parsing_stats.bot_statistics:
                        text += (
                            f"\n<b>{bot_stat['bot_name']}</b>\n"
                            f"   • Транзакций: {bot_stat['transaction_count']} ({bot_stat['percentage_of_total']}%)\n"
                            f"   • Конвертировано: {bot_stat['total_converted_amount']:.2f}\n"
                        )

                text += f"\n💡 Используйте /parsing_stats [24h|7d|30d]"
                await update.message.reply_text(text, parse_mode="HTML")

            except Exception as e:
                logger.error("Error in parsing stats command", error=str(e), user_id=user.id)
                await update.message.reply_text(
                    "❌ <b>Ошибка</b>\n\nПроизошла ошибка при получении статистики.",
                    parse_mode="HTML",
                )

    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /broadcast — рассылка сообщения всем пользователям."""
        user = update.effective_user
        logger.info("Broadcast command requested", user_id=user.id)

        with build_services() as svc:
            if not svc.admin_service.is_admin(user.id):
                await update.message.reply_text(
                    "❌ <b>Доступ запрещен</b>\n\nЭта команда доступна только администраторам.",
                    parse_mode="HTML",
                )
                return

            if not context.args:
                await update.message.reply_text(
                    "❌ <b>Не указан текст сообщения</b>\n\n"
                    "Использование: /broadcast &lt;текст&gt;",
                    parse_mode="HTML",
                )
                return

            broadcast_message = " ".join(context.args)

            try:
                from core.services.broadcast_service import BroadcastService
                broadcast_service = BroadcastService(svc.user_repo)

                await update.message.reply_text(
                    f"📢 <b>Начинаю рассылку...</b>\n\n"
                    f"<b>Сообщение:</b>\n{broadcast_message}\n\n⏳ Пожалуйста, подождите...",
                    parse_mode="HTML",
                )

                result = await broadcast_service.broadcast_to_all(broadcast_message, user.id)

                if result:
                    success_rate = (result.successful_sends / max(result.total_users, 1)) * 100
                    text = (
                        f"✅ <b>Рассылка завершена!</b>\n\n"
                        f"📊 <b>Статистика:</b>\n"
                        f"   • Всего пользователей: {result.total_users}\n"
                        f"   • Успешно: {result.successful_sends}\n"
                        f"   • Ошибок: {result.failed_sends}\n"
                        f"   • Успех: {success_rate:.1f}%\n"
                        f"⏱️ Время: {result.execution_time:.2f} сек"
                    )
                    await update.message.reply_text(text, parse_mode="HTML")
                else:
                    await update.message.reply_text(
                        "❌ <b>Ошибка рассылки</b>\n\nПопробуйте позже.",
                        parse_mode="HTML",
                    )

            except Exception as e:
                logger.error("Error in broadcast command", error=str(e), user_id=user.id)
                await update.message.reply_text(
                    "❌ <b>Ошибка</b>\n\nПроизошла ошибка при рассылке.",
                    parse_mode="HTML",
                )

    async def user_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /user_stats — детальная статистика пользователя."""
        user = update.effective_user
        logger.info("User stats command requested", user_id=user.id)

        with build_services() as svc:
            if not svc.admin_service.is_admin(user.id):
                await update.message.reply_text(
                    "❌ <b>Доступ запрещен</b>\n\nЭта команда доступна только администраторам.",
                    parse_mode="HTML",
                )
                return

            if not context.args:
                await update.message.reply_text(
                    "❌ <b>Не указан пользователь</b>\n\n"
                    "Использование: /user_stats &lt;@username&gt;",
                    parse_mode="HTML",
                )
                return

            target_username = context.args[0].strip()

            try:
                from core.services.admin_stats_service import AdminStatsService
                admin_stats_service = AdminStatsService(svc.user_repo)
                user_stats = await admin_stats_service.get_user_stats(target_username)

                if not user_stats:
                    await update.message.reply_text(
                        f"❌ <b>Пользователь не найден</b>\n\n"
                        f"Пользователь '{target_username}' не найден в системе.",
                        parse_mode="HTML",
                    )
                    return

                text = (
                    f"👤 <b>Статистика пользователя</b>\n\n"
                    f"🆔 <b>ID:</b> {user_stats.user_id}\n"
                    f"👤 <b>Имя:</b> {user_stats.first_name or 'Не указано'}\n"
                    f"📝 <b>Username:</b> @{user_stats.username or 'Не указан'}\n"
                    f"📅 <b>Регистрация:</b> {user_stats.created_at[:19].replace('T', ' ')}\n"
                    f"🕐 <b>Активность:</b> {user_stats.last_activity[:19].replace('T', ' ')}\n\n"
                    f"💰 <b>Финансы:</b>\n"
                    f"   • Баланс: {user_stats.current_balance:.2f} монет\n"
                    f"   • Заработано: {user_stats.total_earned:.2f} монет\n"
                    f"   • Покупок: {user_stats.total_purchases}\n\n"
                    f"🏆 <b>Статус:</b>\n"
                    f"   • Администратор: {'✅' if user_stats.is_admin else '❌'}\n"
                    f"   • VIP: {'✅' if user_stats.is_vip else '❌'}\n"
                    f"   • Дневная серия: {user_stats.daily_streak} дней"
                )
                await update.message.reply_text(text, parse_mode="HTML")

            except Exception as e:
                logger.error("Error in user stats command", error=str(e), user_id=user.id)
                await update.message.reply_text(
                    "❌ <b>Ошибка</b>\n\nПроизошла ошибка при получении статистики.",
                    parse_mode="HTML",
                )

    async def add_item_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /add_item — добавление товара в магазин."""
        user = update.effective_user
        logger.info("Add item command requested", user_id=user.id)

        with build_services() as svc:
            if not svc.admin_service.is_admin(user.id):
                await update.message.reply_text(
                    "❌ <b>Доступ запрещен</b>\n\nЭта команда доступна только администраторам.",
                    parse_mode="HTML",
                )
                return

            if not context.args or len(context.args) < 3:
                await update.message.reply_text(
                    "❌ <b>Неверные параметры</b>\n\n"
                    "<b>Использование:</b> /add_item &lt;название&gt; &lt;цена&gt; &lt;тип&gt;\n\n"
                    "<b>Типы:</b> sticker, admin, mention_all, custom",
                    parse_mode="HTML",
                )
                return

            try:
                args = context.args
                valid_types = {"sticker", "admin", "mention_all", "custom"}
                item_type = args[-1].lower()

                if item_type not in valid_types:
                    raise ValueError(f"Недопустимый тип. Допустимые: {', '.join(valid_types)}")

                try:
                    price = int(args[-2])
                    if price <= 0:
                        raise ValueError("Цена должна быть положительной")
                except (ValueError, TypeError):
                    raise ValueError("Неверный формат цены")

                name = " ".join(args[:-2]).strip('"\'')
                if not name:
                    raise ValueError("Название не может быть пустым")

            except ValueError as e:
                await update.message.reply_text(
                    f"❌ <b>Ошибка в параметрах</b>\n\n{e}",
                    parse_mode="HTML",
                )
                return

            try:
                result = await svc.shop_service.add_item(name, price, item_type)

                if result["success"]:
                    item = result["item"]
                    await update.message.reply_text(
                        f"✅ <b>Товар добавлен!</b>\n\n"
                        f"🆔 ID: {item['id']}\n"
                        f"📝 Название: {item['name']}\n"
                        f"💰 Цена: {item['price']} монет\n"
                        f"🏷️ Тип: {item['item_type']}",
                        parse_mode="HTML",
                    )
                else:
                    await update.message.reply_text(
                        f"❌ <b>Ошибка</b>\n\n{result.get('message', 'Не удалось добавить товар')}",
                        parse_mode="HTML",
                    )

            except Exception as e:
                logger.error("Error in add item command", error=str(e), user_id=user.id)
                await update.message.reply_text(
                    "❌ <b>Ошибка</b>\n\nПроизошла ошибка при добавлении товара.",
                    parse_mode="HTML",
                )
