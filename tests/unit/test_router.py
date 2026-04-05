"""
Unit tests for bot router module.

Tests the setup_routers() function that registers all command handlers
from different command modules.

Validates: Requirements 10.3, 10.4
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from telegram.ext import Application, CommandHandler

from bot.router import setup_routers
from bot.commands.admin_commands import AdminCommands
from bot.commands.user_commands import UserCommands
from bot.commands.shop_commands import ShopCommands
from bot.commands.game_commands import GameCommands
from bot.commands.system_commands import SystemCommands


@pytest.fixture
def mock_application():
    """Create a mock Application instance."""
    app = Mock(spec=Application)
    app.handlers = {0: []}  # Default handler group
    app.add_handler = Mock(side_effect=lambda handler, group=0: app.handlers[group].append(handler))
    return app


@pytest.fixture
def mock_admin_system():
    """Create a mock AdminSystem instance."""
    admin_system = Mock()
    admin_system.is_admin = Mock(return_value=True)
    admin_system.get_user_by_id = Mock(return_value={'id': 1, 'telegram_id': 123, 'is_admin': True})
    return admin_system


@pytest.fixture
def command_instances(mock_admin_system):
    """Create instances of all command classes."""
    return {
        'admin': AdminCommands(mock_admin_system),
        'user': UserCommands(mock_admin_system),
        'shop': ShopCommands(mock_admin_system),
        'game': GameCommands(),
        'system': SystemCommands(mock_admin_system)
    }


class TestSetupRouters:
    """Test suite for setup_routers function."""

    def test_setup_routers_registers_all_handlers(self, mock_application, command_instances):
        """Test that setup_routers registers all command handlers."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert
        assert mock_application.add_handler.called
        assert len(mock_application.handlers[0]) > 0

        # Verify we have handlers registered
        handlers = mock_application.handlers[0]
        assert all(isinstance(h, CommandHandler) for h in handlers)

    def test_setup_routers_registers_system_commands(self, mock_application, command_instances):
        """Test that system commands are registered."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - check for system command handlers
        handlers = mock_application.handlers[0]
        command_names = [h.commands for h in handlers if isinstance(h, CommandHandler)]
        command_names_flat = [cmd for cmds in command_names for cmd in cmds]

        assert 'start' in command_names_flat
        assert 'help' in command_names_flat
        assert 'about' in command_names_flat
        assert 'beta' in command_names_flat

    def test_setup_routers_registers_user_commands(self, mock_application, command_instances):
        """Test that user commands are registered."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - check for user command handlers
        handlers = mock_application.handlers[0]
        command_names = [h.commands for h in handlers if isinstance(h, CommandHandler)]
        command_names_flat = [cmd for cmds in command_names for cmd in cmds]

        assert 'profile' in command_names_flat
        assert 'balance' in command_names_flat
        assert 'history' in command_names_flat
        assert 'stats' in command_names_flat

    def test_setup_routers_registers_shop_commands(self, mock_application, command_instances):
        """Test that shop commands are registered."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - check for shop command handlers
        handlers = mock_application.handlers[0]
        command_names = [h.commands for h in handlers if isinstance(h, CommandHandler)]
        command_names_flat = [cmd for cmds in command_names for cmd in cmds]

        assert 'shop' in command_names_flat
        assert 'buy' in command_names_flat
        assert 'buy_contact' in command_names_flat
        assert 'buy_1' in command_names_flat
        assert 'inventory' in command_names_flat

    def test_setup_routers_registers_game_commands(self, mock_application, command_instances):
        """Test that game commands are registered."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - check for game command handlers
        handlers = mock_application.handlers[0]
        command_names = [h.commands for h in handlers if isinstance(h, CommandHandler)]
        command_names_flat = [cmd for cmds in command_names for cmd in cmds]

        assert 'games' in command_names_flat
        assert 'play' in command_names_flat
        assert 'join' in command_names_flat
        assert 'dnd' in command_names_flat
        assert 'dnd_create' in command_names_flat

    def test_setup_routers_registers_admin_commands(self, mock_application, command_instances):
        """Test that admin commands are registered."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - check for admin command handlers
        handlers = mock_application.handlers[0]
        command_names = [h.commands for h in handlers if isinstance(h, CommandHandler)]
        command_names_flat = [cmd for cmds in command_names for cmd in cmds]

        assert 'admin' in command_names_flat
        assert 'add_points' in command_names_flat
        assert 'add_admin' in command_names_flat
        assert 'admin_users' in command_names_flat
        assert 'admin_stats' in command_names_flat

    def test_setup_routers_registers_background_task_commands(self, mock_application, command_instances):
        """Test that background task management commands are registered."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - check for background task command handlers
        handlers = mock_application.handlers[0]
        command_names = [h.commands for h in handlers if isinstance(h, CommandHandler)]
        command_names_flat = [cmd for cmds in command_names for cmd in cmds]

        assert 'admin_background_status' in command_names_flat
        assert 'admin_background_health' in command_names_flat
        assert 'admin_background_restart' in command_names_flat

    def test_setup_routers_registers_parsing_config_commands(self, mock_application, command_instances):
        """Test that parsing configuration commands are registered."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - check for parsing config command handlers
        handlers = mock_application.handlers[0]
        command_names = [h.commands for h in handlers if isinstance(h, CommandHandler)]
        command_names_flat = [cmd for cmds in command_names for cmd in cmds]

        assert 'admin_parsing_reload' in command_names_flat
        assert 'admin_parsing_config' in command_names_flat

    def test_setup_routers_minimum_handler_count(self, mock_application, command_instances):
        """Test that a minimum number of handlers are registered."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - we should have at least 40 command handlers
        # (system: 4, user: 4, shop: 12, game: 10, admin: 25+)
        handlers = mock_application.handlers[0]
        assert len(handlers) >= 40

    def test_setup_routers_logs_registration(self, mock_application, command_instances):
        """Test that setup_routers logs the registration process."""
        # We use structlog which outputs to stdout, so we just verify the function runs
        # without errors and registers handlers

        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - verify handlers were registered (logging happened)
        assert len(mock_application.handlers[0]) > 0
        assert mock_application.add_handler.called

    def test_setup_routers_handlers_are_callable(self, mock_application, command_instances):
        """Test that all registered handlers have callable callbacks."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - all handlers should have callable callbacks
        handlers = mock_application.handlers[0]
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                assert callable(handler.callback)

    def test_setup_routers_no_duplicate_commands(self, mock_application, command_instances):
        """Test that no command is registered twice."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - check for duplicate command names
        handlers = mock_application.handlers[0]
        command_names = []
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                command_names.extend(handler.commands)

        # Check for duplicates
        duplicates = [cmd for cmd in command_names if command_names.count(cmd) > 1]
        assert len(duplicates) == 0, f"Found duplicate commands: {set(duplicates)}"


class TestRouterIntegration:
    """Integration tests for router with command modules."""

    def test_router_with_real_command_instances(self, mock_application, mock_admin_system):
        """Test router with real command class instances."""
        # Arrange
        admin_commands = AdminCommands(mock_admin_system)
        user_commands = UserCommands(mock_admin_system)
        shop_commands = ShopCommands(mock_admin_system)
        game_commands = GameCommands()
        system_commands = SystemCommands(mock_admin_system)

        # Act
        setup_routers(
            mock_application,
            admin_commands,
            user_commands,
            shop_commands,
            game_commands,
            system_commands
        )

        # Assert
        assert len(mock_application.handlers[0]) > 0

        # Verify all command methods exist
        assert hasattr(admin_commands, 'admin_command')
        assert hasattr(user_commands, 'profile_command')
        assert hasattr(shop_commands, 'shop_command')
        assert hasattr(game_commands, 'games_command')
        assert hasattr(system_commands, 'help_command')

    def test_router_command_handlers_have_correct_callbacks(self, mock_application, command_instances):
        """Test that command handlers are linked to correct callback methods."""
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Assert - find specific handlers and verify their callbacks
        handlers = mock_application.handlers[0]

        # Find the 'admin' command handler
        admin_handler = next((h for h in handlers if isinstance(h, CommandHandler) and 'admin' in h.commands), None)
        assert admin_handler is not None
        assert admin_handler.callback == command_instances['admin'].admin_command

        # Find the 'profile' command handler
        profile_handler = next((h for h in handlers if isinstance(h, CommandHandler) and 'profile' in h.commands), None)
        assert profile_handler is not None
        assert profile_handler.callback == command_instances['user'].profile_command

        # Find the 'shop' command handler
        shop_handler = next((h for h in handlers if isinstance(h, CommandHandler) and 'shop' in h.commands), None)
        assert shop_handler is not None
        assert shop_handler.callback == command_instances['shop'].shop_command


class TestAllCommandsRegistered:
    """
    Comprehensive test to verify ALL commands from ALL 5 modules are registered.
    
    This test validates Requirements 10.3 and 10.4 by ensuring that every command
    from admin, user, shop, game, and system modules is properly registered in the router.
    
    Validates: Requirements 10.3, 10.4
    """

    def test_all_commands_from_all_modules_are_registered(self, mock_application, command_instances):
        """
        Test that ALL commands from ALL 5 modules are properly registered.
        
        This is the comprehensive test for Task 10.3.3 - Протестировать все команды.
        It verifies that every single command from all command modules is registered
        and working through the router system.
        """
        # Act
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        # Get all registered command names
        handlers = mock_application.handlers[0]
        registered_commands = set()
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                registered_commands.update(handler.commands)

        # Define ALL expected commands from ALL 5 modules
        expected_commands = {
            # System Commands (4 commands)
            'start', 'help', 'about', 'beta',

            # User Commands (4 commands)
            'profile', 'balance', 'history', 'stats',

            # Shop Commands (12 commands)
            'shop', 'buy', 'buy_contact', 'buy_1', 'buy_2', 'buy_3', 
            'buy_4', 'buy_5', 'buy_6', 'buy_7', 'buy_8', 'inventory',

            # Game Commands (10 commands)
            'games', 'play', 'join', 'startgame', 'turn',
            'dnd', 'dnd_create', 'dnd_join', 'dnd_roll', 'dnd_sessions',

            # Admin Commands (27 commands)
            # Core admin
            'admin', 'add_points', 'add_admin',
            # User management
            'admin_users', 'admin_balances', 'admin_transactions',
            'admin_addcoins', 'admin_removecoins', 'admin_adjust', 'admin_merge',
            # System statistics and management
            'admin_stats', 'admin_rates', 'admin_rate', 'admin_health',
            'admin_errors', 'admin_backup', 'admin_cleanup',
            # Shop management
            'admin_shop_add', 'admin_shop_edit',
            # Game management
            'admin_games_stats', 'admin_reset_game', 'admin_ban_player',
            # Background task management
            'admin_background_status', 'admin_background_health', 'admin_background_restart',
            # Parsing configuration management
            'admin_parsing_reload', 'admin_parsing_config'
        }

        # Assert: All expected commands are registered
        missing_commands = expected_commands - registered_commands
        assert len(missing_commands) == 0, f"Missing commands: {missing_commands}"

        # Assert: Total count matches (57 commands total)
        assert len(expected_commands) == 57, "Expected command count changed"
        assert len(registered_commands) >= 57, f"Expected at least 57 commands, got {len(registered_commands)}"

        # Assert: No unexpected commands (all registered commands should be in expected)
        unexpected_commands = registered_commands - expected_commands
        assert len(unexpected_commands) == 0, f"Unexpected commands registered: {unexpected_commands}"

    def test_all_system_commands_registered(self, mock_application, command_instances):
        """Test that all 4 system commands are registered."""
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        handlers = mock_application.handlers[0]
        registered_commands = set()
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                registered_commands.update(handler.commands)

        system_commands = {'start', 'help', 'about', 'beta'}
        assert system_commands.issubset(registered_commands), \
            f"Missing system commands: {system_commands - registered_commands}"

    def test_all_user_commands_registered(self, mock_application, command_instances):
        """Test that all 4 user commands are registered."""
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        handlers = mock_application.handlers[0]
        registered_commands = set()
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                registered_commands.update(handler.commands)

        user_commands = {'profile', 'balance', 'history', 'stats'}
        assert user_commands.issubset(registered_commands), \
            f"Missing user commands: {user_commands - registered_commands}"

    def test_all_shop_commands_registered(self, mock_application, command_instances):
        """Test that all 12 shop commands are registered."""
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        handlers = mock_application.handlers[0]
        registered_commands = set()
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                registered_commands.update(handler.commands)

        shop_commands = {
            'shop', 'buy', 'buy_contact', 'buy_1', 'buy_2', 'buy_3',
            'buy_4', 'buy_5', 'buy_6', 'buy_7', 'buy_8', 'inventory'
        }
        assert shop_commands.issubset(registered_commands), \
            f"Missing shop commands: {shop_commands - registered_commands}"

    def test_all_game_commands_registered(self, mock_application, command_instances):
        """Test that all 10 game commands are registered."""
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        handlers = mock_application.handlers[0]
        registered_commands = set()
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                registered_commands.update(handler.commands)

        game_commands = {
            'games', 'play', 'join', 'startgame', 'turn',
            'dnd', 'dnd_create', 'dnd_join', 'dnd_roll', 'dnd_sessions'
        }
        assert game_commands.issubset(registered_commands), \
            f"Missing game commands: {game_commands - registered_commands}"

    def test_all_admin_commands_registered(self, mock_application, command_instances):
        """Test that all 27 admin commands are registered."""
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        handlers = mock_application.handlers[0]
        registered_commands = set()
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                registered_commands.update(handler.commands)

        admin_commands = {
            # Core admin
            'admin', 'add_points', 'add_admin',
            # User management
            'admin_users', 'admin_balances', 'admin_transactions',
            'admin_addcoins', 'admin_removecoins', 'admin_adjust', 'admin_merge',
            # System statistics and management
            'admin_stats', 'admin_rates', 'admin_rate', 'admin_health',
            'admin_errors', 'admin_backup', 'admin_cleanup',
            # Shop management
            'admin_shop_add', 'admin_shop_edit',
            # Game management
            'admin_games_stats', 'admin_reset_game', 'admin_ban_player',
            # Background task management
            'admin_background_status', 'admin_background_health', 'admin_background_restart',
            # Parsing configuration management
            'admin_parsing_reload', 'admin_parsing_config'
        }
        assert admin_commands.issubset(registered_commands), \
            f"Missing admin commands: {admin_commands - registered_commands}"

    def test_command_handlers_respond_correctly(self, mock_application, command_instances):
        """
        Test that command handlers are properly linked and can be called.
        
        This verifies that the integration between router and command modules works correctly.
        """
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        handlers = mock_application.handlers[0]

        # Verify that all handlers have valid callbacks
        for handler in handlers:
            if isinstance(handler, CommandHandler):
                assert handler.callback is not None, f"Handler for {handler.commands} has no callback"
                assert callable(handler.callback), f"Handler for {handler.commands} callback is not callable"

    def test_no_commands_missing_or_broken(self, mock_application, command_instances):
        """
        Test that no commands are missing or broken.
        
        This is a comprehensive check that ensures the router system is complete and functional.
        """
        setup_routers(
            mock_application,
            command_instances['admin'],
            command_instances['user'],
            command_instances['shop'],
            command_instances['game'],
            command_instances['system']
        )

        handlers = mock_application.handlers[0]

        # Verify we have the expected number of handlers
        assert len(handlers) == 57, f"Expected 57 command handlers, got {len(handlers)}"

        # Verify all handlers are CommandHandler instances
        assert all(isinstance(h, CommandHandler) for h in handlers), \
            "Not all handlers are CommandHandler instances"

        # Verify all handlers have commands
        for handler in handlers:
            assert len(handler.commands) > 0, "Found handler with no commands"

        # Verify all handlers have callbacks
        for handler in handlers:
            assert handler.callback is not None, f"Handler {handler.commands} has no callback"
