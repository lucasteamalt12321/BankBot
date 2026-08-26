"""
Integration tests for main.py startup validation and signal handling

Покрывает реальное поведение bot/main.py:
- Startup validation (validate_startup) вызывается перед запуском бота
  и при провале — main завершается с ненулевым кодом (печатает ошибку).
- Порядок операций при старте: миграция схемы БД -> валидация -> завершение
  старых процессов -> создание и запуск бота.
- BotApplication.shutdown() корректно останавливает ресурсы и удаляет PID-файл.
- BotApplication.setup_signal_handlers() регистрирует SIGTERM/SIGINT и
  устанавливает shutdown_event (graceful shutdown, Requirements 9.2, 9.4).

Validates: Requirements 8.2 - Integration of validation in main.py
Validates: Requirements 9.2, 9.4 - Signal handling for graceful shutdown
Validates: Design section 8 - Environment validation at startup
Validates: Design section 9 - Graceful shutdown with signal handling
"""

import os
import sys
import signal
import asyncio
import pytest
from unittest.mock import patch, MagicMock, call, Mock

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_main_with_mocks(validate_return=True, kill_return=False, run_raises=KeyboardInterrupt()):
    """
    Запускает main() с замоканными зависимостями и возвращает использованные моки.
    run_raises — исключение, которое бросает bot.run() (по умолчанию KeyboardInterrupt,
    чтобы имитировать штатную остановку).
    """
    with patch('bot.main.validate_startup') as mock_validate, \
         patch('bot.main.kill_existing_bot_processes') as mock_kill, \
         patch('bot.main.ensure_schema_up_to_date') as mock_schema, \
         patch('bot.main.TelegramBot') as mock_bot:

        mock_validate.return_value = validate_return
        mock_kill.return_value = kill_return
        mock_bot_instance = MagicMock()
        mock_bot.return_value = mock_bot_instance
        if run_raises is not None:
            mock_bot_instance.run.side_effect = run_raises

        try:
            from bot.main import main
            main()
        except KeyboardInterrupt:
            pass
        except Exception:
            pass

        return {
            'validate': mock_validate,
            'kill': mock_kill,
            'schema': mock_schema,
            'bot': mock_bot,
            'bot_instance': mock_bot_instance,
        }


class TestMainStartupValidation:
    """Test startup validation integration in main.py"""

    def test_main_calls_startup_validator(self):
        """Test that main() calls validate_startup()"""
        mocks = run_main_with_mocks()
        mocks['validate'].assert_called_once()

    def test_main_exits_on_validation_failure(self):
        """Test that main() exits when validation fails"""
        from bot.main import main

        with patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes'), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot'):

            mock_validate.side_effect = SystemExit(1)

            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    def test_main_does_not_start_bot_on_validation_failure(self):
        """Test that bot is not started if validation fails"""
        from bot.main import main

        with patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes') as mock_kill, \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:

            mock_validate.side_effect = SystemExit(1)

            with pytest.raises(SystemExit):
                main()

            # Bot should not be created or started
            mock_bot.assert_not_called()
            # Process killing should not happen (validation happens before kill)
            mock_kill.assert_not_called()

    def test_main_validates_before_killing_processes(self):
        """Test that validation happens before killing old processes"""
        from bot.main import main

        call_order = []

        def track_validate(*args, **kwargs):
            call_order.append('validate')
            return True

        def track_kill(*args, **kwargs):
            call_order.append('kill')
            return False

        with patch('bot.main.validate_startup', side_effect=track_validate), \
             patch('bot.main.kill_existing_bot_processes', side_effect=track_kill), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass

            # Validation should happen before killing processes
            assert call_order.index('validate') < call_order.index('kill')

    def test_main_schema_migration_runs_before_validation(self):
        """Test that DB schema migration runs before validation (and both before bot)"""
        from bot.main import main

        call_order = []

        def track_schema(*args, **kwargs):
            call_order.append('schema')

        def track_validate(*args, **kwargs):
            call_order.append('validate')
            return True

        def track_kill(*args, **kwargs):
            call_order.append('kill')
            return False

        with patch('bot.main.validate_startup', side_effect=track_validate), \
             patch('bot.main.kill_existing_bot_processes', side_effect=track_kill), \
             patch('bot.main.ensure_schema_up_to_date', side_effect=track_schema), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass

            # Schema migration (DB setup) runs first, then validation, then kill
            assert 'schema' in call_order
            assert 'validate' in call_order
            assert call_order.index('schema') < call_order.index('validate')
            assert call_order.index('validate') < call_order.index('kill')


class TestSignalHandling:
    """Test signal handling in BotApplication (Task 9.2.1)"""

    def test_signal_handlers_are_registered(self):
        """
        Test that SIGTERM and SIGINT handlers are registered
        Validates: Requirements 9.2, 9.4
        """
        from bot.main import BotApplication

        with patch('signal.signal') as mock_signal:
            app = BotApplication()
            app.setup_signal_handlers()

            assert mock_signal.call_count == 2
            calls = [c[0][0] for c in mock_signal.call_args_list]
            assert signal.SIGTERM in calls
            assert signal.SIGINT in calls

    def test_sigterm_sets_shutdown_event(self):
        """
        Test that SIGTERM signal sets shutdown event
        Validates: Requirements 9.2, 9.4
        """
        from bot.main import BotApplication

        app = BotApplication()

        with patch('signal.signal') as mock_signal:
            app.setup_signal_handlers()

            sigterm_handler = None
            for call_args in mock_signal.call_args_list:
                if call_args[0][0] == signal.SIGTERM:
                    sigterm_handler = call_args[0][1]
                    break

            assert sigterm_handler is not None
            sigterm_handler(signal.SIGTERM, None)
            assert app.shutdown_event.is_set()

    def test_sigint_sets_shutdown_event(self):
        """
        Test that SIGINT signal sets shutdown event
        Validates: Requirements 9.2, 9.4
        """
        from bot.main import BotApplication

        app = BotApplication()

        with patch('signal.signal') as mock_signal:
            app.setup_signal_handlers()

            sigint_handler = None
            for call_args in mock_signal.call_args_list:
                if call_args[0][0] == signal.SIGINT:
                    sigint_handler = call_args[0][1]
                    break

            assert sigint_handler is not None
            sigint_handler(signal.SIGINT, None)
            assert app.shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_shutdown_removes_pid_file(self):
        """
        Test that shutdown removes PID file
        Validates: Requirements 9.3
        """
        from bot.main import BotApplication

        with patch('bot.main.ProcessManager.remove_pid') as mock_remove:
            app = BotApplication()
            await app.shutdown()
            mock_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_stops_bot_application(self):
        """
        Test that shutdown stops bot application
        Validates: Requirements 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        mock_bot = MagicMock()
        mock_application = MagicMock()
        mock_application.running = True

        async def mock_stop():
            pass

        mock_application.stop = mock_stop
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('bot.main.ProcessManager.remove_pid'), \
             patch.object(mock_application, 'stop', wraps=mock_stop) as mock_stop_spy:
            await app.shutdown()
            mock_stop_spy.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_missing_bot(self):
        """
        Test that shutdown handles case when bot is not initialized
        Validates: Requirements 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()
        app.bot = None

        with patch('bot.main.ProcessManager.remove_pid') as mock_remove:
            await app.shutdown()
            mock_remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_errors_gracefully(self):
        """
        Test that shutdown handles errors and still removes PID file
        Validates: Requirements 9.3
        """
        from bot.main import BotApplication

        app = BotApplication()

        mock_bot = MagicMock()
        mock_application = MagicMock()
        mock_application.running = True

        async def failing_stop():
            raise Exception("Test error")

        mock_application.stop = failing_stop
        mock_bot.application = mock_application
        app.bot = mock_bot

        with patch('bot.main.ProcessManager.remove_pid') as mock_remove:
            await app.shutdown()
            mock_remove.assert_called_once()


class TestProcessManagerIntegration:
    """Test ProcessManager integration in main.py (Task 9.1, 9.2)"""

    def test_main_kills_existing_process_before_startup(self):
        """
        Test that main kills existing process before starting
        Validates: Requirements 9.1
        """
        from bot.main import main

        with patch('bot.main.validate_startup'), \
             patch('bot.main.kill_existing_bot_processes') as mock_kill, \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_kill.return_value = True
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass
            mock_kill.assert_called_once()

    def test_main_runs_schema_migration_on_startup(self):
        """
        Test that main runs DB schema migration on startup
        Validates: Requirements 8.2
        """
        from bot.main import main

        with patch('bot.main.validate_startup'), \
             patch('bot.main.kill_existing_bot_processes') as mock_kill, \
             patch('bot.main.ensure_schema_up_to_date') as mock_schema, \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass
            mock_schema.assert_called_once()

    def test_main_creates_bot_instance(self):
        """
        Test that main creates and runs the bot instance
        Validates: Requirements 9.1, 9.2
        """
        from bot.main import main

        with patch('bot.main.validate_startup'), \
             patch('bot.main.kill_existing_bot_processes') as mock_kill, \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass
            mock_bot.assert_called_once()
            mock_bot_instance.run.assert_called_once()

    def test_main_propagates_bot_run_errors(self):
        """
        Test that main propagates errors raised during bot.run()
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import main

        with patch('bot.main.validate_startup'), \
             patch('bot.main.kill_existing_bot_processes'), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = RuntimeError("Bot crashed")

            with pytest.raises(RuntimeError):
                main()


class TestMainWithDifferentConfigurations:
    """Test main.py with different configuration scenarios"""

    def test_main_with_valid_configuration(self):
        """Test main() with valid configuration"""
        from bot.main import main

        with patch.dict(os.environ, {
            'BOT_TOKEN': 'test_token_12345',
            'ADMIN_TELEGRAM_ID': '123456789',
            'DATABASE_URL': 'sqlite:///test.db',
            'ENV': 'test'
        }), \
             patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes') as mock_kill, \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_validate.return_value = True
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass
            mock_bot.assert_called_once()

    def test_main_with_missing_env_file(self):
        """Test main() exits when startup validation fails (env/.env missing)"""
        from bot.main import main

        with patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes'), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot'):
            mock_validate.side_effect = SystemExit(1)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_with_missing_bot_token(self):
        """Test main() exits when BOT_TOKEN validation fails"""
        from bot.main import main

        with patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes'), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot'):
            mock_validate.side_effect = SystemExit(1)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_with_invalid_database_url(self):
        """Test main() exits when database validation fails"""
        from bot.main import main

        with patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes'), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot'):
            mock_validate.side_effect = SystemExit(1)
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_main_with_development_environment(self):
        """Test main() with development environment"""
        from bot.main import main

        with patch.dict(os.environ, {'ENV': 'development'}), \
             patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes') as mock_kill, \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_validate.return_value = True
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass
            mock_validate.assert_called_once()

    def test_main_with_production_environment(self):
        """Test main() with production environment"""
        from bot.main import main

        with patch.dict(os.environ, {'ENV': 'production'}), \
             patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes') as mock_kill, \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_validate.return_value = True
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass
            mock_validate.assert_called_once()

    def test_main_with_test_environment(self):
        """Test main() with test environment"""
        from bot.main import main

        with patch.dict(os.environ, {'ENV': 'test'}), \
             patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes') as mock_kill, \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot') as mock_bot:
            mock_validate.return_value = True
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            try:
                main()
            except KeyboardInterrupt:
                pass
            mock_validate.assert_called_once()


class TestMainErrorHandling:
    """Test error handling in main.py"""

    def test_main_catches_system_exit_from_validator(self):
        """Test that main() surfaces SystemExit from validator"""
        from bot.main import main

        with patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes'), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot'), \
             patch('builtins.print') as mock_print:
            mock_validate.side_effect = SystemExit(1)
            with pytest.raises(SystemExit) as exc_info:
                main()
            error_calls = [c for c in mock_print.call_args_list
                           if 'ERROR' in str(c) or 'validation failed' in str(c).lower()]
            assert len(error_calls) > 0
            assert exc_info.value.code == 1

    def test_main_preserves_exit_code(self):
        """Test that main() preserves the exit code from validator"""
        from bot.main import main

        with patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes'), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot'):
            for exit_code in [1, 2, 3]:
                mock_validate.side_effect = SystemExit(exit_code)
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == exit_code

    def test_main_prints_error_message_on_validation_failure(self):
        """Test that main() prints helpful error message on validation failure"""
        from bot.main import main

        with patch('bot.main.validate_startup') as mock_validate, \
             patch('bot.main.kill_existing_bot_processes'), \
             patch('bot.main.ensure_schema_up_to_date'), \
             patch('bot.main.TelegramBot'), \
             patch('builtins.print') as mock_print:
            mock_validate.side_effect = SystemExit(1)
            with pytest.raises(SystemExit):
                main()
            print_calls = [str(c) for c in mock_print.call_args_list]
            error_printed = any('ERROR' in call or 'validation failed' in call.lower()
                                for call in print_calls)
            assert error_printed, f"No error message found in: {print_calls}"


class TestMainValidationOrder:
    """Test the order of operations in main.py"""

    def test_validation_is_first_operation(self):
        """Test that schema migration and validation are the first operations"""
        from bot.main import main

        operations = []

        def track(name):
            def wrapper(*args, **kwargs):
                operations.append(name)
                if name == 'bot_run':
                    raise KeyboardInterrupt()
                if name == 'bot_init':
                    inst = MagicMock()
                    inst.run.side_effect = lambda: operations.append('bot_run') or (_ for _ in ()).throw(KeyboardInterrupt())
                    return inst
                if name == 'kill':
                    return False
                return MagicMock()
            return wrapper

        with patch('bot.main.validate_startup', side_effect=track('validate')), \
             patch('bot.main.kill_existing_bot_processes', side_effect=track('kill')), \
             patch('bot.main.ensure_schema_up_to_date', side_effect=track('schema')), \
             patch('bot.main.TelegramBot', side_effect=track('bot_init')):
            try:
                main()
            except KeyboardInterrupt:
                pass

        # Schema migration -> validation -> kill -> bot init -> bot run
        assert operations == ['schema', 'validate', 'kill', 'bot_init', 'bot_run']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
