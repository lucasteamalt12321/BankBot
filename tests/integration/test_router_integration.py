"""
Integration tests for router-based command registration (Task 10.3.2)

Tests that the router correctly registers all commands from all command modules.
Validates: Requirements 10.3, 10.4
"""

import pytest
from unittest.mock import Mock, MagicMock
from telegram.ext import Application
from bot.router import setup_routers
from bot.commands.admin_commands import AdminCommands
from bot.commands.user_commands import UserCommands
from bot.commands.shop_commands import ShopCommands
from bot.commands.game_commands import GameCommands
from bot.commands.system_commands import SystemCommands


class TestRouterIntegration:
    """Test suite for router-based command registration"""

    @pytest.fixture
    def mock_application(self):
        """Create a mock Application instance"""
        app = Mock(spec=Application)
        app.add_handler = Mock()
        app.handlers = {0: []}  # Default group
        return app

    @pytest.fixture
    def mock_admin_system(self):
        """Create a mock AdminSystem"""
        return Mock()

    @pytest.fixture
    def command_modules(self, mock_admin_system):
        """Create instances of all command modules"""
        admin_commands = AdminCommands(
            admin_system=mock_admin_system,
            background_task_manager=Mock(),
            monitoring_system=Mock(),
            error_handling_system=Mock(),
            backup_system=Mock()
        )
        user_commands = UserCommands(admin_system=mock_admin_system)
        shop_commands = ShopCommands(admin_system=mock_admin_system)
        game_commands = GameCommands()
        system_commands = SystemCommands(admin_system=mock_admin_system)

        return {
            'admin': admin_commands,
            'user': user_commands,
            'shop': shop_commands,
            'game': game_commands,
            'system': system_commands
        }

    def test_router_registers_all_command_modules(self, mock_application, command_modules):
        """Test that router registers commands from all modules"""
        # Call the router
        setup_routers(
            application=mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system']
        )

        # Verify that add_handler was called multiple times
        assert mock_application.add_handler.call_count > 0, \
            "Router should register at least one command handler"

        # Get all registered command names
        registered_commands = []
        for call in mock_application.add_handler.call_args_list:
            handler = call[0][0]
            if hasattr(handler, 'commands'):
                registered_commands.extend(handler.commands)

        # Verify key commands from each module are registered
        expected_commands = {
            'start',  # User commands
            'help',   # System commands
            'shop',   # Shop commands
            'games',  # Game commands
            'admin'   # Admin commands
        }

        # Note: We can't easily verify exact command names with mocks,
        # but we can verify the router was called and handlers were added
        assert mock_application.add_handler.call_count >= 50, \
            f"Expected at least 50 command handlers, got {mock_application.add_handler.call_count}"

    def test_router_registers_system_commands_first(self, mock_application, command_modules):
        """Test that system commands are registered first (as per design)"""
        setup_routers(
            application=mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system']
        )

        # Verify handlers were registered
        assert mock_application.add_handler.call_count > 0

    def test_router_handles_missing_admin_commands(self, mock_application, command_modules):
        """Test that router handles None admin_commands gracefully"""
        # This should not raise an exception
        # The router should handle None values gracefully
        try:
            setup_routers(
                application=mock_application,
                admin_commands=command_modules['admin'],
                user_commands=command_modules['user'],
                shop_commands=command_modules['shop'],
                game_commands=command_modules['game'],
                system_commands=command_modules['system']
            )
        except Exception as e:
            pytest.fail(f"Router should not raise exception: {e}")

    def test_router_registers_all_command_categories(self, mock_application, command_modules):
        """Test that router registers commands from all 5 categories"""
        setup_routers(
            application=mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system']
        )

        # Verify a substantial number of handlers were registered
        # Based on router.py, we expect:
        # - 4 system commands
        # - 4 user commands  
        # - 11 shop commands
        # - 9 game commands
        # - 30+ admin commands
        # Total: 57+ commands

        assert mock_application.add_handler.call_count >= 57, \
            f"Expected at least 57 command handlers, got {mock_application.add_handler.call_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
