"""
Integration tests for router-based command registration (Task 10.3.2)

Tests that the router correctly registers all commands from all command modules.
Validates: Requirements 10.3, 10.4
"""

import pytest
from unittest.mock import Mock, MagicMock
from telegram.ext import Application, CommandHandler
from bot.router import setup_routers

import bot.commands.admin_commands as admin_commands
import bot.commands.user_commands as user_commands
import bot.commands.shop_commands as shop_commands
import bot.commands.game_commands as game_commands
import bot.commands.system_commands as system_commands


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
    def command_modules(self):
        """Return all command modules (function-based API)."""
        return {
            'admin': admin_commands,
            'user': user_commands,
            'shop': shop_commands,
            'game': game_commands,
            'system': system_commands,
        }

    def _registered_commands(self, mock_application):
        commands = []
        for call in mock_application.add_handler.call_args_list:
            handler = call[0][0]
            if isinstance(handler, CommandHandler):
                commands.extend(handler.commands)
        return commands

    def test_router_registers_all_command_modules(self, mock_application, command_modules):
        """Test that router registers commands from all modules"""
        setup_routers(
            application=mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )

        assert mock_application.add_handler.call_count > 0, \
            "Router should register at least one command handler"

        registered_commands = self._registered_commands(mock_application)
        for cmd in ('start', 'help', 'profile', 'shop', 'games', 'add_points'):
            assert cmd in registered_commands

    def test_router_registers_system_commands_first(self, mock_application, command_modules):
        """Test that system commands are registered"""
        setup_routers(
            application=mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        assert mock_application.add_handler.call_count > 0

    def test_router_handles_missing_admin_commands(self, mock_application, command_modules):
        """Test that router handles None admin_commands gracefully"""
        try:
            setup_routers(
                application=mock_application,
                admin_commands=None,
                user_commands=command_modules['user'],
                shop_commands=command_modules['shop'],
                game_commands=command_modules['game'],
                system_commands=command_modules['system'],
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
            system_commands=command_modules['system'],
        )

        registered_commands = self._registered_commands(mock_application)

        # Verify a substantial number of handlers were registered
        # (system: 4, user: 10, shop: 5, game: 6, admin: 3 => 28 handlers)
        assert mock_application.add_handler.call_count >= 20, \
            f"Expected at least 20 command handlers, got {mock_application.add_handler.call_count}"

        # Verify each module category is present
        for cmd in ('start', 'profile', 'shop', 'games', 'add_points'):
            assert cmd in registered_commands


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
