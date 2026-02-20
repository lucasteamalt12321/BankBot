"""
Тесты для конфигурационных команд бота
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

# Импортируем команды
from bot.commands.config_commands import ConfigurationCommands


@pytest.fixture
def mock_update():
    """Создает mock объект Update"""
    update = Mock(spec=Update)
    update.effective_user = Mock(spec=User)
    update.effective_user.id = 123456789
    update.effective_user.username = "test_admin"
    update.effective_user.first_name = "Test"
    
    update.message = Mock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.message.reply_document = AsyncMock()
    
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 123456789
    
    return update


@pytest.fixture
def mock_context():
    """Создает mock объект Context"""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    context.bot = Mock()
    context.bot.get_file = AsyncMock()
    return context


@pytest.fixture
def config_commands():
    """Создает экземпляр ConfigurationCommands"""
    return ConfigurationCommands()


class TestReloadConfig:
    """Тесты для команды /reload_config"""
    
    @pytest.mark.asyncio
    async def test_reload_config_success(self, config_commands, mock_update, mock_context):
        """Тест успешной перезагрузки конфигурации"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch('bot.commands.config_commands.reload_global_configuration', return_value=True):
                with patch.object(config_commands.config_manager, 'get_validation_errors', return_value=[]):
                    await config_commands.reload_config_command(mock_update, mock_context)
                    
                    # Проверяем, что был вызван reply_text
                    assert mock_update.message.reply_text.called
                    call_args = mock_update.message.reply_text.call_args[0][0]
                    assert "✅" in call_args
                    assert "успешно перезагружена" in call_args
    
    @pytest.mark.asyncio
    async def test_reload_config_no_admin(self, config_commands, mock_update, mock_context):
        """Тест отказа в доступе для не-администратора"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=False):
            await config_commands.reload_config_command(mock_update, mock_context)
            
            # Проверяем сообщение об отказе
            assert mock_update.message.reply_text.called
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "❌" in call_args
            assert "нет прав" in call_args.lower()


class TestConfigStatus:
    """Тесты для команды /config_status"""
    
    @pytest.mark.asyncio
    async def test_config_status_healthy(self, config_commands, mock_update, mock_context):
        """Тест отображения статуса здоровой системы"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            # Мокаем здоровую систему
            mock_health = Mock()
            mock_health.is_healthy = True
            mock_health.database_connected = True
            mock_health.parsing_active = True
            mock_health.background_tasks_running = True
            
            with patch.object(config_commands.config_manager, 'get_health_status', return_value=mock_health):
                with patch.object(config_commands.config_manager, 'get_configuration') as mock_config:
                    mock_config.return_value.parsing_rules = []
                    mock_config.return_value.admin_user_ids = [123456789]
                    
                    await config_commands.config_status_command(mock_update, mock_context)
                    
                    assert mock_update.message.reply_text.called
                    call_args = mock_update.message.reply_text.call_args[0][0]
                    assert "✅" in call_args
                    assert "Здорово" in call_args


class TestListParsingRules:
    """Тесты для команды /list_parsing_rules"""
    
    @pytest.mark.asyncio
    async def test_list_parsing_rules_empty(self, config_commands, mock_update, mock_context):
        """Тест отображения пустого списка правил"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'get_configuration') as mock_config:
                mock_config.return_value.parsing_rules = []
                
                await config_commands.list_parsing_rules_command(mock_update, mock_context)
                
                assert mock_update.message.reply_text.called
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "не настроены" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_list_parsing_rules_with_rules(self, config_commands, mock_update, mock_context):
        """Тест отображения списка правил"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            # Создаем mock правила
            mock_rule = Mock()
            mock_rule.id = 1
            mock_rule.bot_name = "TestBot"
            mock_rule.pattern = "Test: (\\d+)"
            mock_rule.multiplier = 1.5
            mock_rule.currency_type = "points"
            mock_rule.is_active = True
            
            with patch.object(config_commands.config_manager, 'get_configuration') as mock_config:
                mock_config.return_value.parsing_rules = [mock_rule]
                
                await config_commands.list_parsing_rules_command(mock_update, mock_context)
                
                assert mock_update.message.reply_text.called
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "TestBot" in call_args
                assert "1.5" in str(call_args)


class TestAddParsingRule:
    """Тесты для команды /add_parsing_rule"""
    
    @pytest.mark.asyncio
    async def test_add_parsing_rule_success(self, config_commands, mock_update, mock_context):
        """Тест успешного добавления правила"""
        mock_context.args = ["TestBot", "Pattern: (\\d+)", "1.5", "points"]
        
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'add_parsing_rule', return_value=True):
                await config_commands.add_parsing_rule_command(mock_update, mock_context)
                
                assert mock_update.message.reply_text.called
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "✅" in call_args
                assert "успешно добавлено" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_add_parsing_rule_invalid_args(self, config_commands, mock_update, mock_context):
        """Тест с неверными аргументами"""
        mock_context.args = ["TestBot"]  # Недостаточно аргументов
        
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            await config_commands.add_parsing_rule_command(mock_update, mock_context)
            
            assert mock_update.message.reply_text.called
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "❌" in call_args
            assert "Неверный формат" in call_args


class TestUpdateParsingRule:
    """Тесты для команды /update_parsing_rule"""
    
    @pytest.mark.asyncio
    async def test_update_parsing_rule_success(self, config_commands, mock_update, mock_context):
        """Тест успешного обновления правила"""
        mock_context.args = ["1", "multiplier", "2.0"]
        
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'update_parsing_rule', return_value=True):
                await config_commands.update_parsing_rule_command(mock_update, mock_context)
                
                assert mock_update.message.reply_text.called
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "✅" in call_args
                assert "обновлено" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_update_parsing_rule_invalid_field(self, config_commands, mock_update, mock_context):
        """Тест с неверным полем"""
        mock_context.args = ["1", "invalid_field", "value"]
        
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            await config_commands.update_parsing_rule_command(mock_update, mock_context)
            
            assert mock_update.message.reply_text.called
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "❌" in call_args
            assert "Неверное поле" in call_args


class TestExportConfig:
    """Тесты для команды /export_config"""
    
    @pytest.mark.asyncio
    async def test_export_config_success(self, config_commands, mock_update, mock_context):
        """Тест успешного экспорта конфигурации"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            mock_export_data = {"version": "1.0", "data": "test"}
            with patch.object(config_commands.config_manager, 'export_configuration', return_value=mock_export_data):
                with patch('builtins.open', create=True) as mock_open:
                    with patch('tempfile.NamedTemporaryFile') as mock_temp:
                        mock_temp.return_value.__enter__.return_value.name = '/tmp/test.json'
                        
                        await config_commands.export_config_command(mock_update, mock_context)
                        
                        assert mock_update.message.reply_document.called


class TestBackupConfig:
    """Тесты для команды /backup_config"""
    
    @pytest.mark.asyncio
    async def test_backup_config_success(self, config_commands, mock_update, mock_context):
        """Тест успешного создания бэкапа"""
        mock_context.args = ["Test backup"]
        
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'create_configuration_backup', return_value="backup123"):
                await config_commands.backup_config_command(mock_update, mock_context)
                
                assert mock_update.message.reply_text.called
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "✅" in call_args
                assert "backup123" in call_args


class TestRestoreConfig:
    """Тесты для команды /restore_config"""
    
    @pytest.mark.asyncio
    async def test_restore_config_success(self, config_commands, mock_update, mock_context):
        """Тест успешного восстановления из бэкапа"""
        mock_context.args = ["backup123"]
        
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'restore_configuration_backup', return_value=True):
                await config_commands.restore_config_command(mock_update, mock_context)
                
                assert mock_update.message.reply_text.called
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "✅" in call_args
                assert "восстановлена" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_restore_config_no_args(self, config_commands, mock_update, mock_context):
        """Тест без указания ID бэкапа"""
        mock_context.args = []
        
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            await config_commands.restore_config_command(mock_update, mock_context)
            
            assert mock_update.message.reply_text.called
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "❌" in call_args
            assert "укажите ID" in call_args.lower()


class TestListBackups:
    """Тесты для команды /list_backups"""
    
    @pytest.mark.asyncio
    async def test_list_backups_empty(self, config_commands, mock_update, mock_context):
        """Тест с пустым списком бэкапов"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'list_configuration_backups', return_value=[]):
                await config_commands.list_backups_command(mock_update, mock_context)
                
                assert mock_update.message.reply_text.called
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "не найдены" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_list_backups_with_backups(self, config_commands, mock_update, mock_context):
        """Тест со списком бэкапов"""
        mock_backups = [
            {
                'backup_id': 'backup123',
                'description': 'Test backup',
                'created_at': '2026-02-20T14:30:25Z',
                'file_size': 15360
            }
        ]
        
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'list_configuration_backups', return_value=mock_backups):
                await config_commands.list_backups_command(mock_update, mock_context)
                
                assert mock_update.message.reply_text.called
                call_args = mock_update.message.reply_text.call_args[0][0]
                assert "backup123" in call_args
                assert "Test backup" in call_args


class TestValidateConfig:
    """Тесты для команды /validate_config"""
    
    @pytest.mark.asyncio
    async def test_validate_config_success(self, config_commands, mock_update, mock_context):
        """Тест успешной валидации"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'get_configuration') as mock_config:
                mock_config.return_value.parsing_rules = []
                mock_config.return_value.admin_user_ids = [123456789]
                
                with patch.object(config_commands.config_manager, 'validate_configuration', return_value=[]):
                    with patch.object(config_commands.config_manager, 'validate_configuration_schema', return_value=[]):
                        await config_commands.validate_config_command(mock_update, mock_context)
                        
                        assert mock_update.message.reply_text.called
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "✅" in call_args
                        assert "пройдена" in call_args.lower()
    
    @pytest.mark.asyncio
    async def test_validate_config_with_errors(self, config_commands, mock_update, mock_context):
        """Тест валидации с ошибками"""
        with patch.object(config_commands.admin_manager, 'is_admin', return_value=True):
            with patch.object(config_commands.config_manager, 'get_configuration') as mock_config:
                mock_config.return_value.parsing_rules = []
                
                errors = ["Error 1", "Error 2"]
                with patch.object(config_commands.config_manager, 'validate_configuration', return_value=errors):
                    with patch.object(config_commands.config_manager, 'validate_configuration_schema', return_value=[]):
                        await config_commands.validate_config_command(mock_update, mock_context)
                        
                        assert mock_update.message.reply_text.called
                        call_args = mock_update.message.reply_text.call_args[0][0]
                        assert "❌" in call_args
                        assert "не пройдена" in call_args.lower()
                        assert "Error 1" in call_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
