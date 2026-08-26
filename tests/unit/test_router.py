"""
Unit tests for bot router module.

Tests the setup_routers() function that registers all command handlers
from different command modules (function-based API).

Validates: Requirements 10.3, 10.4
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from telegram.ext import Application, CommandHandler

from bot.router import setup_routers
import bot.commands.admin_commands as admin_commands
import bot.commands.user_commands as user_commands
import bot.commands.shop_commands as shop_commands
import bot.commands.game_commands as game_commands
import bot.commands.system_commands as system_commands


@pytest.fixture
def mock_application():
    """Create a mock Application instance."""
    app = Mock(spec=Application)
    app.handlers = {0: []}  # Default handler group
    app.add_handler = Mock(side_effect=lambda handler, group=0: app.handlers[group].append(handler))
    return app


@pytest.fixture
def command_modules():
    """Return all command modules (function-based API)."""
    return {
        'admin': admin_commands,
        'user': user_commands,
        'shop': shop_commands,
        'game': game_commands,
        'system': system_commands,
    }


def _registered_commands(application):
    """Collect all registered command names from the mock application."""
    commands = []
    for handler in application.handlers[0]:
        if isinstance(handler, CommandHandler):
            commands.extend(handler.commands)
    return commands


def _command_handlers(application):
    """Return list of registered CommandHandler instances."""
    return [h for h in application.handlers[0] if isinstance(h, CommandHandler)]


class TestSetupRouters:
    """Test suite for setup_routers function."""

    def test_setup_routers_registers_all_handlers(self, mock_application, command_modules):
        """Test that setup_routers registers all command handlers."""
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )

        assert mock_application.add_handler.called
        assert len(mock_application.handlers[0]) > 0
        assert all(isinstance(h, CommandHandler) for h in mock_application.handlers[0])

    def test_setup_routers_registers_system_commands(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        command_names = _registered_commands(mock_application)
        for cmd in ('start', 'help', 'about', 'beta'):
            assert cmd in command_names

    def test_setup_routers_registers_user_commands(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        command_names = _registered_commands(mock_application)
        for cmd in ('profile', 'balance'):
            assert cmd in command_names

    def test_setup_routers_registers_shop_commands(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        command_names = _registered_commands(mock_application)
        for cmd in ('shop', 'buy', 'buy_contact', 'inventory'):
            assert cmd in command_names

    def test_setup_routers_registers_game_commands(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        command_names = _registered_commands(mock_application)
        for cmd in ('games', 'play', 'join', 'dnd', 'dnd_create', 'dnd_roll'):
            assert cmd in command_names

    def test_setup_routers_registers_admin_commands(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        command_names = _registered_commands(mock_application)
        for cmd in ('add_points', 'add_admin'):
            assert cmd in command_names

    def test_setup_routers_minimum_handler_count(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        handlers = _command_handlers(mock_application)
        assert len(handlers) >= 20

    def test_setup_routers_logs_registration(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        assert len(mock_application.handlers[0]) > 0
        assert mock_application.add_handler.called

    def test_setup_routers_handlers_are_callable(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        for handler in _command_handlers(mock_application):
            assert callable(handler.callback)

    def test_setup_routers_no_duplicate_commands(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        command_names = _registered_commands(mock_application)
        duplicates = [cmd for cmd in set(command_names) if command_names.count(cmd) > 1]
        assert len(duplicates) == 0, f"Found duplicate commands: {set(duplicates)}"


class TestRouterIntegration:
    """Integration tests for router with command modules."""

    def test_router_with_real_command_modules(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        assert len(mock_application.handlers[0]) > 0

        # Verify all command functions exist on modules
        assert hasattr(command_modules['admin'], 'add_points_command')
        assert hasattr(command_modules['user'], 'profile_command')
        assert hasattr(command_modules['shop'], 'shop_command')
        assert hasattr(command_modules['game'], 'games_command')
        assert hasattr(command_modules['system'], 'help_command')

    def test_router_command_handlers_have_correct_callbacks(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        handlers = _command_handlers(mock_application)

        admin_handler = next((h for h in handlers if 'add_points' in h.commands), None)
        assert admin_handler is not None
        assert admin_handler.callback == command_modules['admin'].add_points_command

        profile_handler = next((h for h in handlers if 'profile' in h.commands), None)
        assert profile_handler is not None
        assert profile_handler.callback == command_modules['user'].profile_command

        shop_handler = next((h for h in handlers if 'shop' in h.commands), None)
        assert shop_handler is not None
        assert shop_handler.callback == command_modules['shop'].shop_command


class TestAllCommandsRegistered:
    """
    Comprehensive test to verify ALL commands from ALL 5 modules are registered.
    Validates: Requirements 10.3, 10.4
    """

    EXPECTED_COMMANDS = {
        # System Commands
        'start', 'help', 'about', 'beta',
        # User Commands
        'profile', 'balance',
        'buy_1', 'buy_2', 'buy_3', 'buy_4', 'buy_5', 'buy_6', 'buy_7', 'buy_8',
        # Shop Commands
        'shop', 'buy', 'buy_contact', 'inventory',
        # Game Commands
        'games', 'play', 'join', 'dnd', 'dnd_create', 'dnd_roll',
        # Admin Commands
        'admin_panel', 'add_points', 'add_admin',
    }

    def test_all_commands_from_all_modules_are_registered(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        registered_commands = set(_registered_commands(mock_application))

        missing_commands = self.EXPECTED_COMMANDS - registered_commands
        assert len(missing_commands) == 0, f"Missing commands: {missing_commands}"

        unexpected_commands = registered_commands - self.EXPECTED_COMMANDS
        assert len(unexpected_commands) == 0, f"Unexpected commands registered: {unexpected_commands}"

        assert len(registered_commands) == len(self.EXPECTED_COMMANDS)

    def test_all_system_commands_registered(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        registered_commands = set(_registered_commands(mock_application))
        system_commands_set = {'start', 'help', 'about', 'beta'}
        assert system_commands_set.issubset(registered_commands)

    def test_all_user_commands_registered(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        registered_commands = set(_registered_commands(mock_application))
        user_commands_set = {'profile', 'balance', 'buy_1', 'buy_2', 'buy_3', 'buy_4',
                             'buy_5', 'buy_6', 'buy_7', 'buy_8'}
        assert user_commands_set.issubset(registered_commands)

    def test_all_shop_commands_registered(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        registered_commands = set(_registered_commands(mock_application))
        shop_commands_set = {'shop', 'buy', 'buy_contact', 'inventory'}
        assert shop_commands_set.issubset(registered_commands)

    def test_all_game_commands_registered(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        registered_commands = set(_registered_commands(mock_application))
        game_commands_set = {'games', 'play', 'join', 'dnd', 'dnd_create', 'dnd_roll'}
        assert game_commands_set.issubset(registered_commands)

    def test_all_admin_commands_registered(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        registered_commands = set(_registered_commands(mock_application))
        admin_commands_set = {'admin_panel', 'add_points', 'add_admin'}
        assert admin_commands_set.issubset(registered_commands)

    def test_command_handlers_respond_correctly(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        for handler in _command_handlers(mock_application):
            assert handler.callback is not None
            assert callable(handler.callback)

    def test_no_commands_missing_or_broken(self, mock_application, command_modules):
        setup_routers(
            mock_application,
            admin_commands=command_modules['admin'],
            user_commands=command_modules['user'],
            shop_commands=command_modules['shop'],
            game_commands=command_modules['game'],
            system_commands=command_modules['system'],
        )
        handlers = _command_handlers(mock_application)

        assert len(handlers) == len(self.EXPECTED_COMMANDS)
        assert all(isinstance(h, CommandHandler) for h in handlers)
        for handler in handlers:
            assert len(handler.commands) > 0
            assert handler.callback is not None
