"""
Configuration management commands for Advanced Telegram Bot Features
Provides admin commands for managing parsing rules and configuration
"""

import os
import sys
import json
import tempfile
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Any
from telegram import Update
from telegram.ext import ContextTypes
import structlog

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.managers.config_manager import get_config_manager, reload_global_configuration
from core.managers.admin_manager import AdminManager
from database.database import get_db

logger = structlog.get_logger()


class ConfigurationCommands:
    """
    Configuration management commands for administrators
    Implements Requirements 11.1, 11.2, 11.3, 11.4, 11.5
    """
    
    def __init__(self):
        """Initialize configuration commands"""
        self.config_manager = get_config_manager()
        self.admin_manager = AdminManager()
    
    async def reload_config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to reload configuration without restart
        Usage: /reload_config
        
        Validates: Requirements 11.3
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            logger.info("Admin requested configuration reload", admin_id=user_id)
            
            # Send initial message
            status_message = await update.message.reply_text("🔄 Перезагружаю конфигурацию...")
            
            # Reload configuration
            success = reload_global_configuration()
            
            # Get validation errors
            errors = self.config_manager.get_validation_errors()
            
            if success and not errors:
                response_text = (
                    "✅ Конфигурация успешно перезагружена!\n\n"
                    f"📊 Статистика:\n"
                    f"• Правила парсинга: {len(self.config_manager.get_configuration().parsing_rules)}\n"
                    f"• Администраторы: {len(self.config_manager.get_configuration().admin_user_ids)}\n"
                    f"• Время перезагрузки: {self.config_manager.last_reload_time.strftime('%H:%M:%S')}"
                )
            elif success and errors:
                response_text = (
                    "⚠️ Конфигурация перезагружена с предупреждениями:\n\n"
                    f"🔍 Ошибки валидации:\n"
                )
                for i, error in enumerate(errors[:5], 1):  # Show max 5 errors
                    response_text += f"{i}. {error}\n"
                
                if len(errors) > 5:
                    response_text += f"... и еще {len(errors) - 5} ошибок"
            else:
                response_text = (
                    "❌ Не удалось перезагрузить конфигурацию!\n\n"
                    f"🔍 Ошибки:\n"
                )
                for i, error in enumerate(errors[:3], 1):  # Show max 3 errors
                    response_text += f"{i}. {error}\n"
            
            await status_message.edit_text(response_text)
            
        except Exception as e:
            logger.error("Error in reload config command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при перезагрузке конфигурации: {str(e)}")
    
    async def config_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to show configuration status
        Usage: /config_status
        
        Validates: Requirements 11.4
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            logger.info("Admin requested configuration status", admin_id=user_id)
            
            # Get configuration and health status
            config = self.config_manager.get_configuration()
            health = self.config_manager.get_health_status()
            errors = self.config_manager.get_validation_errors()
            
            # Build status message
            status_icon = "✅" if health.is_healthy else "❌"
            response_text = f"{status_icon} **Статус конфигурации**\n\n"
            
            # Health indicators
            response_text += "🏥 **Состояние системы:**\n"
            response_text += f"• Общее состояние: {'✅ Здорово' if health.is_healthy else '❌ Проблемы'}\n"
            response_text += f"• База данных: {'✅ Подключена' if health.database_connected else '❌ Отключена'}\n"
            response_text += f"• Парсинг: {'✅ Активен' if health.parsing_active else '❌ Неактивен'}\n"
            response_text += f"• Фоновые задачи: {'✅ Работают' if health.background_tasks_running else '❌ Остановлены'}\n\n"
            
            # Configuration details
            response_text += "⚙️ **Параметры конфигурации:**\n"
            response_text += f"• Правила парсинга: {len(config.parsing_rules)}\n"
            response_text += f"• Администраторы: {len(config.admin_user_ids)}\n"
            response_text += f"• Интервал очистки стикеров: {config.sticker_cleanup_interval}с\n"
            response_text += f"• Задержка удаления стикеров: {config.sticker_auto_delete_delay}с\n"
            response_text += f"• Размер пакета рассылки: {config.broadcast_batch_size}\n"
            response_text += f"• Максимум попыток парсинга: {config.max_parsing_retries}\n\n"
            
            # Last reload time
            if self.config_manager.last_reload_time:
                response_text += f"🕐 **Последняя перезагрузка:** {self.config_manager.last_reload_time.strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            
            # Validation errors
            if errors:
                response_text += f"⚠️ **Ошибки валидации ({len(errors)}):**\n"
                for i, error in enumerate(errors[:3], 1):  # Show max 3 errors
                    response_text += f"{i}. {error}\n"
                
                if len(errors) > 3:
                    response_text += f"... и еще {len(errors) - 3} ошибок\n"
            
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error("Error in config status command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при получении статуса конфигурации: {str(e)}")
    
    async def list_parsing_rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to list all parsing rules
        Usage: /list_parsing_rules
        
        Validates: Requirements 11.1
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            logger.info("Admin requested parsing rules list", admin_id=user_id)
            
            # Get parsing rules
            config = self.config_manager.get_configuration()
            rules = config.parsing_rules
            
            if not rules:
                await update.message.reply_text("📋 Правила парсинга не настроены.")
                return
            
            # Build rules list
            response_text = f"📋 **Правила парсинга ({len(rules)}):**\n\n"
            
            for i, rule in enumerate(rules, 1):
                status_icon = "✅" if rule.is_active else "❌"
                response_text += f"{status_icon} **{i}. {rule.bot_name}**\n"
                response_text += f"   • ID: {rule.id}\n"
                response_text += f"   • Паттерн: `{rule.pattern}`\n"
                response_text += f"   • Множитель: {rule.multiplier}\n"
                response_text += f"   • Тип валюты: {rule.currency_type}\n"
                response_text += f"   • Статус: {'Активно' if rule.is_active else 'Неактивно'}\n\n"
            
            # Split message if too long
            if len(response_text) > 4000:
                # Send in chunks
                chunks = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='Markdown')
            else:
                await update.message.reply_text(response_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error("Error in list parsing rules command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при получении списка правил парсинга: {str(e)}")
    
    async def add_parsing_rule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to add a new parsing rule
        Usage: /add_parsing_rule <bot_name> <pattern> <multiplier> <currency_type>
        
        Validates: Requirements 11.1, 11.2
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            # Parse command arguments
            if len(context.args) < 4:
                await update.message.reply_text(
                    "❌ Неверный формат команды!\n\n"
                    "**Использование:**\n"
                    "`/add_parsing_rule <bot_name> <pattern> <multiplier> <currency_type>`\n\n"
                    "**Пример:**\n"
                    "`/add_parsing_rule TestBot 'Очки: +(\\d+)' 1.5 points`",
                    parse_mode='Markdown'
                )
                return
            
            bot_name = context.args[0]
            pattern = context.args[1]
            try:
                multiplier = Decimal(context.args[2])
            except (ValueError, IndexError):
                await update.message.reply_text("❌ Неверный формат множителя! Используйте число (например: 1.5)")
                return
            
            currency_type = context.args[3]
            
            logger.info(
                "Admin adding new parsing rule",
                admin_id=user_id,
                bot_name=bot_name,
                pattern=pattern,
                multiplier=multiplier,
                currency_type=currency_type
            )
            
            # Add parsing rule
            success = self.config_manager.add_parsing_rule(bot_name, pattern, multiplier, currency_type)
            
            if success:
                response_text = (
                    "✅ Правило парсинга успешно добавлено!\n\n"
                    f"🤖 **Бот:** {bot_name}\n"
                    f"🔍 **Паттерн:** `{pattern}`\n"
                    f"💰 **Множитель:** {multiplier}\n"
                    f"💎 **Тип валюты:** {currency_type}\n\n"
                    "Правило активно и готово к использованию."
                )
            else:
                response_text = (
                    "❌ Не удалось добавить правило парсинга!\n\n"
                    "Возможные причины:\n"
                    "• Правило с таким паттерном уже существует\n"
                    "• Ошибка валидации данных\n"
                    "• Проблема с базой данных"
                )
            
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error("Error in add parsing rule command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при добавлении правила парсинга: {str(e)}")
    
    async def update_parsing_rule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to update an existing parsing rule
        Usage: /update_parsing_rule <rule_id> <field> <value>
        
        Validates: Requirements 11.1, 11.2
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            # Parse command arguments
            if len(context.args) < 3:
                await update.message.reply_text(
                    "❌ Неверный формат команды!\n\n"
                    "**Использование:**\n"
                    "`/update_parsing_rule <rule_id> <field> <value>`\n\n"
                    "**Доступные поля:**\n"
                    "• `bot_name` - название бота\n"
                    "• `pattern` - регулярное выражение\n"
                    "• `multiplier` - множитель конвертации\n"
                    "• `currency_type` - тип валюты\n"
                    "• `is_active` - статус (true/false)\n\n"
                    "**Пример:**\n"
                    "`/update_parsing_rule 1 multiplier 2.0`",
                    parse_mode='Markdown'
                )
                return
            
            try:
                rule_id = int(context.args[0])
            except ValueError:
                await update.message.reply_text("❌ Неверный ID правила! Используйте число.")
                return
            
            field = context.args[1]
            value = context.args[2]
            
            # Validate field
            valid_fields = ['bot_name', 'pattern', 'multiplier', 'currency_type', 'is_active']
            if field not in valid_fields:
                await update.message.reply_text(f"❌ Неверное поле! Доступные поля: {', '.join(valid_fields)}")
                return
            
            # Convert value based on field type
            if field == 'multiplier':
                try:
                    value = Decimal(value)
                except ValueError:
                    await update.message.reply_text("❌ Неверный формат множителя! Используйте число.")
                    return
            elif field == 'is_active':
                value = value.lower() in ['true', '1', 'yes', 'да']
            
            logger.info(
                "Admin updating parsing rule",
                admin_id=user_id,
                rule_id=rule_id,
                field=field,
                value=value
            )
            
            # Update parsing rule
            success = self.config_manager.update_parsing_rule(rule_id, **{field: value})
            
            if success:
                response_text = (
                    "✅ Правило парсинга успешно обновлено!\n\n"
                    f"🆔 **ID правила:** {rule_id}\n"
                    f"📝 **Поле:** {field}\n"
                    f"🔄 **Новое значение:** {value}\n\n"
                    "Изменения применены немедленно."
                )
            else:
                response_text = (
                    "❌ Не удалось обновить правило парсинга!\n\n"
                    "Возможные причины:\n"
                    "• Правило с указанным ID не найдено\n"
                    "• Ошибка валидации данных\n"
                    "• Проблема с базой данных"
                )
            
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error("Error in update parsing rule command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при обновлении правила парсинга: {str(e)}")
    
    async def export_config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to export current configuration
        Usage: /export_config [no-rules]
        
        Validates: Requirements 11.2, 11.4
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            logger.info("Admin requested configuration export", admin_id=user_id)
            
            # Parse command arguments
            include_rules = True
            if context.args and context.args[0].lower() == 'no-rules':
                include_rules = False
            
            # Export configuration
            export_data = self.config_manager.export_configuration(include_parsing_rules=include_rules)
            
            if not export_data:
                await update.message.reply_text("❌ Не удалось экспортировать конфигурацию.")
                return
            
            # Create export file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                export_file = f.name
            
            # Send file to admin
            with open(export_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename=f"bot_config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    caption=f"📤 **Экспорт конфигурации**\n"
                           f"🕒 Создан: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                           f"📋 Правила парсинга: {'Включены' if include_rules else 'Исключены'}"
                )
            
            # Clean up temporary file
            os.unlink(export_file)
            
            logger.info("Configuration exported successfully", admin_id=user_id)
            
        except Exception as e:
            logger.error("Error in export config command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при экспорте конфигурации: {str(e)}")
    
    async def import_config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to import configuration from file
        Usage: /import_config [with-rules] (send as caption to JSON file)
        
        Validates: Requirements 11.2, 11.4
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            # Check if a file was provided
            if not update.message.document:
                await update.message.reply_text(
                    "📁 Пожалуйста, отправьте файл конфигурации с командой /import_config.\n\n"
                    "**Использование:**\n"
                    "1. Отправьте JSON файл конфигурации\n"
                    "2. В подписи к файлу напишите `/import_config` или `/import_config with-rules`\n\n"
                    "**Параметры:**\n"
                    "• `with-rules` - импортировать правила парсинга"
                )
                return
            
            logger.info("Admin requested configuration import", admin_id=user_id)
            
            # Download the file
            file = await context.bot.get_file(update.message.document.file_id)
            
            with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp_file:
                await file.download_to_drive(temp_file.name)
                temp_file_path = temp_file.name
            
            # Read and parse the configuration file
            try:
                with open(temp_file_path, 'r', encoding='utf-8') as f:
                    import_data = json.load(f)
            except json.JSONDecodeError as e:
                await update.message.reply_text(f"❌ Неверный формат JSON файла: {str(e)}")
                os.unlink(temp_file_path)
                return
            
            # Parse command arguments
            import_rules = False
            if context.args and context.args[0].lower() == 'with-rules':
                import_rules = True
            
            # Import configuration
            success = self.config_manager.import_configuration(import_data, import_parsing_rules=import_rules)
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            if success:
                await update.message.reply_text(
                    f"✅ Конфигурация успешно импортирована!\n\n"
                    f"📋 Правила парсинга: {'Импортированы' if import_rules else 'Пропущены'}\n"
                    f"🔄 Конфигурация перезагружена.\n"
                    f"🕒 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                )
                logger.info("Configuration imported successfully", admin_id=user_id)
            else:
                await update.message.reply_text("❌ Не удалось импортировать конфигурацию. Проверьте логи для деталей.")
                logger.error("Configuration import failed", admin_id=user_id)
            
        except Exception as e:
            logger.error("Error in import config command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при импорте конфигурации: {str(e)}")
    
    async def backup_config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to create configuration backup
        Usage: /backup_config [description]
        
        Validates: Requirements 11.2, 11.5
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            logger.info("Admin requested configuration backup", admin_id=user_id)
            
            # Parse description from command arguments
            description = ' '.join(context.args) if context.args else f"Ручной бэкап от администратора {user_id}"
            
            backup_id = self.config_manager.create_configuration_backup(description, created_by=user_id)
            
            if backup_id:
                await update.message.reply_text(
                    f"✅ Бэкап конфигурации создан успешно!\n\n"
                    f"🆔 **ID бэкапа:** `{backup_id}`\n"
                    f"📝 **Описание:** {description}\n"
                    f"🕒 **Создан:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                    "Используйте `/restore_config {backup_id}` для восстановления."
                )
                logger.info("Configuration backup created", backup_id=backup_id, admin_id=user_id)
            else:
                await update.message.reply_text("❌ Не удалось создать бэкап конфигурации.")
                logger.error("Configuration backup failed", admin_id=user_id)
            
        except Exception as e:
            logger.error("Error in backup config command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при создании бэкапа: {str(e)}")
    
    async def restore_config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to restore configuration from backup
        Usage: /restore_config <backup_id>
        
        Validates: Requirements 11.2, 11.5
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            # Parse backup ID from command arguments
            if not context.args:
                await update.message.reply_text(
                    "❌ Пожалуйста, укажите ID бэкапа.\n\n"
                    "**Использование:**\n"
                    "`/restore_config <backup_id>`\n\n"
                    "Используйте `/list_backups` для просмотра доступных бэкапов."
                )
                return
            
            backup_id = context.args[0]
            logger.info("Admin requested configuration restore", backup_id=backup_id, admin_id=user_id)
            
            success = self.config_manager.restore_configuration_backup(backup_id)
            
            if success:
                await update.message.reply_text(
                    f"✅ Конфигурация восстановлена успешно!\n\n"
                    f"🆔 **ID бэкапа:** `{backup_id}`\n"
                    f"🔄 Конфигурация перезагружена.\n"
                    f"🕒 **Восстановлено:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
                )
                logger.info("Configuration restored from backup", backup_id=backup_id, admin_id=user_id)
            else:
                await update.message.reply_text(f"❌ Не удалось восстановить конфигурацию из бэкапа: {backup_id}")
                logger.error("Configuration restore failed", backup_id=backup_id, admin_id=user_id)
            
        except Exception as e:
            logger.error("Error in restore config command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при восстановлении конфигурации: {str(e)}")
    
    async def list_backups_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to list available configuration backups
        Usage: /list_backups
        
        Validates: Requirements 11.2, 11.5
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            logger.info("Admin requested backup list", admin_id=user_id)
            
            backups = self.config_manager.list_configuration_backups()
            
            if not backups:
                await update.message.reply_text("📂 Бэкапы конфигурации не найдены.")
                return
            
            # Format backup list
            response_text = f"📂 **Бэкапы конфигурации ({len(backups)}):**\n\n"
            
            for i, backup in enumerate(backups[:10], 1):  # Show max 10 backups
                created_at = backup.get('created_at', 'Неизвестно')
                if created_at != 'Неизвестно':
                    try:
                        created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = created_dt.strftime('%d.%m.%Y %H:%M:%S')
                    except:
                        pass
                
                file_size = backup.get('file_size', 0)
                size_kb = file_size / 1024 if file_size else 0
                
                backup_id = backup.get('backup_id', 'Неизвестно')
                short_id = backup_id[:8] + '...' if len(backup_id) > 8 else backup_id
                
                response_text += f"{i}. **{short_id}**\n"
                response_text += f"   📝 {backup.get('description', 'Без описания')}\n"
                response_text += f"   🕒 {created_at}\n"
                response_text += f"   📊 {size_kb:.1f} КБ\n\n"
            
            if len(backups) > 10:
                response_text += f"... и еще {len(backups) - 10} бэкапов\n\n"
            
            response_text += "Используйте `/restore_config <backup_id>` для восстановления."
            
            await update.message.reply_text(response_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error("Error in list backups command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при получении списка бэкапов: {str(e)}")
    
    async def validate_config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin command to validate current configuration
        Usage: /validate_config
        
        Validates: Requirements 11.4
        """
        try:
            user_id = update.effective_user.id
            
            # Check admin privileges
            if not self.admin_manager.is_admin(user_id):
                await update.message.reply_text("❌ У вас нет прав администратора для выполнения этой команды.")
                return
            
            logger.info("Admin requested configuration validation", admin_id=user_id)
            
            config = self.config_manager.get_configuration()
            
            # Perform comprehensive validation
            validation_errors = self.config_manager.validate_configuration(config)
            schema_errors = self.config_manager.validate_configuration_schema(config)
            
            all_errors = validation_errors + schema_errors
            
            if not all_errors:
                await update.message.reply_text(
                    "✅ **Валидация конфигурации пройдена**\n\n"
                    f"📋 Правила парсинга: {len(config.parsing_rules)}\n"
                    f"👥 Администраторы: {len(config.admin_user_ids)}\n"
                    f"🧹 Интервал очистки: {config.sticker_cleanup_interval}с\n"
                    f"⏰ Задержка удаления: {config.sticker_auto_delete_delay}с\n"
                    f"📤 Размер пакета: {config.broadcast_batch_size}\n"
                    f"🔄 Макс. попыток: {config.max_parsing_retries}\n\n"
                    "Все настройки конфигурации корректны! ✨",
                    parse_mode='Markdown'
                )
            else:
                error_list = '\n'.join([f"• {error}" for error in all_errors[:10]])
                if len(all_errors) > 10:
                    error_list += f"\n... и еще {len(all_errors) - 10} ошибок"
                
                await update.message.reply_text(
                    f"❌ **Валидация конфигурации не пройдена**\n\n"
                    f"Найдено {len(all_errors)} ошибок валидации:\n\n"
                    f"{error_list}\n\n"
                    "Пожалуйста, исправьте эти проблемы и перезагрузите конфигурацию.",
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error("Error in validate config command", error=str(e))
            await update.message.reply_text(f"❌ Ошибка при валидации конфигурации: {str(e)}")


# Global configuration commands instance
config_commands = ConfigurationCommands()


# Command handler functions for bot registration
async def reload_config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /reload_config command"""
    await config_commands.reload_config_command(update, context)


async def config_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /config_status command"""
    await config_commands.config_status_command(update, context)


async def list_parsing_rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /list_parsing_rules command"""
    await config_commands.list_parsing_rules_command(update, context)


async def add_parsing_rule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /add_parsing_rule command"""
    await config_commands.add_parsing_rule_command(update, context)


async def update_parsing_rule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /update_parsing_rule command"""
    await config_commands.update_parsing_rule_command(update, context)


async def export_config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /export_config command"""
    await config_commands.export_config_command(update, context)


async def import_config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /import_config command"""
    await config_commands.import_config_command(update, context)


async def backup_config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /backup_config command"""
    await config_commands.backup_config_command(update, context)


async def restore_config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /restore_config command"""
    await config_commands.restore_config_command(update, context)


async def list_backups_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /list_backups command"""
    await config_commands.list_backups_command(update, context)


async def validate_config_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /validate_config command"""
    await config_commands.validate_config_command(update, context)