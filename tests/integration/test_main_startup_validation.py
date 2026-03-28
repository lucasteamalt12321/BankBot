"""
Integration tests for main.py startup validation and signal handling

Tests cover:
- Startup validation is called before bot initialization
- Different configuration scenarios (valid, missing env, invalid settings)
- Error handling and exit behavior
- Integration with StartupValidator
- Signal handling (SIGTERM, SIGINT)
- ProcessManager integration

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


class TestMainStartupValidation:
    """Test startup validation integration in main.py"""
    
    def test_main_calls_startup_validator(self):
        """Test that main() calls StartupValidator.validate_all()"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid') as mock_write_pid, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove_pid, \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot') as mock_bot:
            
            mock_validate.return_value = True
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            
            # Mock run to prevent actual bot startup
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            
            try:
                main()
            except KeyboardInterrupt:
                pass
            
            # Verify validation was called
            mock_validate.assert_called_once()
    
    def test_main_exits_on_validation_failure(self):
        """Test that main() exits when validation fails"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing'), \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot'):
            
            # Simulate validation failure
            mock_validate.side_effect = SystemExit(1)
            
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
    
    def test_main_does_not_start_bot_on_validation_failure(self):
        """Test that bot is not started if validation fails"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid') as mock_write_pid, \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove_pid, \
             patch('bot.main.create_tables') as mock_create, \
             patch('bot.main.TelegramBot') as mock_bot:
            
            # Simulate validation failure
            mock_validate.side_effect = SystemExit(1)
            
            with pytest.raises(SystemExit):
                main()
            
            # Bot should not be created or started
            mock_bot.assert_not_called()
            # Process killing should not happen (validation happens first)
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
        
        with patch('bot.main.StartupValidator.validate_all', side_effect=track_validate), \
             patch('bot.main.ProcessManager.kill_existing', side_effect=track_kill), \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot') as mock_bot:
            
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            
            try:
                main()
            except KeyboardInterrupt:
                pass
            
            # Validation should happen before killing processes
            assert call_order == ['validate', 'kill']
    
    def test_main_validates_before_creating_tables(self):
        """Test that validation happens before creating database tables"""
        from bot.main import main
        
        call_order = []
        
        def track_validate(*args, **kwargs):
            call_order.append('validate')
            return True
        
        def track_create(*args, **kwargs):
            call_order.append('create_tables')
        
        with patch('bot.main.StartupValidator.validate_all', side_effect=track_validate), \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables', side_effect=track_create), \
             patch('bot.main.TelegramBot') as mock_bot:
            
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            
            try:
                main()
            except KeyboardInterrupt:
                pass
            
            # Validation should happen before creating tables
            assert 'validate' in call_order
            assert 'create_tables' in call_order
            assert call_order.index('validate') < call_order.index('create_tables')


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
            
            # Verify both signals are registered
            assert mock_signal.call_count == 2
            calls = [call[0] for call in mock_signal.call_args_list]
            assert (signal.SIGTERM, ) in [c[:1] for c in calls]
            assert (signal.SIGINT, ) in [c[:1] for c in calls]
    
    def test_sigterm_sets_shutdown_event(self):
        """
        Test that SIGTERM signal sets shutdown event
        Validates: Requirements 9.2, 9.4
        """
        from bot.main import BotApplication
        import asyncio
        
        app = BotApplication()
        
        # Capture the signal handler
        with patch('signal.signal') as mock_signal:
            app.setup_signal_handlers()
            
            # Get the SIGTERM handler
            sigterm_handler = None
            for call_args in mock_signal.call_args_list:
                if call_args[0][0] == signal.SIGTERM:
                    sigterm_handler = call_args[0][1]
                    break
            
            assert sigterm_handler is not None
            
            # Call the handler
            sigterm_handler(signal.SIGTERM, None)
            
            # Verify shutdown event is set
            assert app.shutdown_event.is_set()
    
    def test_sigint_sets_shutdown_event(self):
        """
        Test that SIGINT signal sets shutdown event
        Validates: Requirements 9.2, 9.4
        """
        from bot.main import BotApplication
        import asyncio
        
        app = BotApplication()
        
        # Capture the signal handler
        with patch('signal.signal') as mock_signal:
            app.setup_signal_handlers()
            
            # Get the SIGINT handler
            sigint_handler = None
            for call_args in mock_signal.call_args_list:
                if call_args[0][0] == signal.SIGINT:
                    sigint_handler = call_args[0][1]
                    break
            
            assert sigint_handler is not None
            
            # Call the handler
            sigint_handler(signal.SIGINT, None)
            
            # Verify shutdown event is set
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
            
            # Verify PID file is removed
            mock_remove.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_stops_bot_application(self):
        """
        Test that shutdown stops bot application
        Validates: Requirements 9.3
        """
        from bot.main import BotApplication
        
        app = BotApplication()
        
        # Create mock bot with application
        mock_bot = MagicMock()
        mock_application = MagicMock()
        mock_application.running = True
        
        # Create async mock for stop
        async def mock_stop():
            pass
        
        mock_application.stop = mock_stop
        mock_bot.application = mock_application
        app.bot = mock_bot
        
        with patch('bot.main.ProcessManager.remove_pid'), \
             patch.object(mock_application, 'stop', wraps=mock_stop) as mock_stop_spy:
            await app.shutdown()
            
            # Verify bot application stop was called
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
            # Should not raise exception
            await app.shutdown()
            
            # PID file should still be removed
            mock_remove.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_handles_errors_gracefully(self):
        """
        Test that shutdown handles errors and still removes PID file
        Validates: Requirements 9.3
        """
        from bot.main import BotApplication
        
        app = BotApplication()
        
        # Create mock bot that raises error on stop
        mock_bot = MagicMock()
        mock_application = MagicMock()
        mock_application.running = True
        
        async def failing_stop():
            raise Exception("Test error")
        
        mock_application.stop = failing_stop
        mock_bot.application = mock_application
        app.bot = mock_bot
        
        with patch('bot.main.ProcessManager.remove_pid') as mock_remove:
            # Should not raise exception
            await app.shutdown()
            
            # PID file should still be removed even on error
            mock_remove.assert_called_once()


class TestProcessManagerIntegration:
    """Test ProcessManager integration in main.py (Task 9.1, 9.2)"""
    
    def test_main_writes_pid_on_startup(self):
        """
        Test that main writes PID file on startup
        Validates: Requirements 9.1, 9.2
        """
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all'), \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid') as mock_write_pid, \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot') as mock_bot:
            
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            
            try:
                main()
            except KeyboardInterrupt:
                pass
            
            # Verify PID was written
            mock_write_pid.assert_called_once()
    
    def test_main_kills_existing_process_before_startup(self):
        """
        Test that main kills existing process before starting
        Validates: Requirements 9.1
        """
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all'), \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid') as mock_write_pid, \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot') as mock_bot:
            
            mock_kill.return_value = True
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            
            try:
                main()
            except KeyboardInterrupt:
                pass
            
            # Verify existing process was killed
            mock_kill.assert_called_once()
    
    def test_main_removes_pid_on_exit(self):
        """
        Test that main removes PID file on exit
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all'), \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove_pid, \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot') as mock_bot:
            
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = KeyboardInterrupt()
            
            try:
                main()
            except KeyboardInterrupt:
                pass
            
            # Verify PID was removed on exit
            mock_remove_pid.assert_called()
    
    def test_main_removes_pid_on_error(self):
        """
        Test that main removes PID file even on error
        Validates: Requirements 9.2, 9.3
        """
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all'), \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid') as mock_remove_pid, \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot') as mock_bot:
            
            mock_kill.return_value = False
            mock_bot_instance = MagicMock()
            mock_bot.return_value = mock_bot_instance
            mock_bot_instance.run.side_effect = Exception("Test error")
            
            try:
                main()
            except Exception:
                pass
            
            # Verify PID was removed even on error
            mock_remove_pid.assert_called()


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
             patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
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
            
            # Should proceed to bot creation
            mock_bot.assert_called_once()
    
    def test_main_with_missing_env_file(self):
        """Test main() exits when .env file is missing"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing'), \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot'):
            
            # Simulate missing env file
            mock_validate.side_effect = SystemExit(1)
            
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
    
    def test_main_with_missing_bot_token(self):
        """Test main() exits when BOT_TOKEN is missing"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing'), \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot'):
            
            # Simulate missing BOT_TOKEN
            mock_validate.side_effect = SystemExit(1)
            
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
    
    def test_main_with_invalid_database_url(self):
        """Test main() exits when database connection fails"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing'), \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot'):
            
            # Simulate database connection failure
            mock_validate.side_effect = SystemExit(1)
            
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            assert exc_info.value.code == 1
    
    def test_main_with_development_environment(self):
        """Test main() with development environment"""
        from bot.main import main
        
        with patch.dict(os.environ, {'ENV': 'development'}), \
             patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
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
            
            # Validation should be called
            mock_validate.assert_called_once()
    
    def test_main_with_production_environment(self):
        """Test main() with production environment"""
        from bot.main import main
        
        with patch.dict(os.environ, {'ENV': 'production'}), \
             patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
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
            
            # Validation should be called
            mock_validate.assert_called_once()
    
    def test_main_with_test_environment(self):
        """Test main() with test environment"""
        from bot.main import main
        
        with patch.dict(os.environ, {'ENV': 'test'}), \
             patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing') as mock_kill, \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
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
            
            # Validation should be called
            mock_validate.assert_called_once()


class TestMainErrorHandling:
    """Test error handling in main.py"""
    
    def test_main_catches_system_exit_from_validator(self):
        """Test that main() catches SystemExit from validator"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing'), \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot'), \
             patch('builtins.print') as mock_print:
            
            mock_validate.side_effect = SystemExit(1)
            
            with pytest.raises(SystemExit) as exc_info:
                main()
            
            # Should print error message
            error_calls = [call for call in mock_print.call_args_list 
                          if 'ERROR' in str(call) or 'validation failed' in str(call).lower()]
            assert len(error_calls) > 0
            
            # Should exit with same code
            assert exc_info.value.code == 1
    
    def test_main_preserves_exit_code(self):
        """Test that main() preserves the exit code from validator"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing'), \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot'):
            
            # Test different exit codes
            for exit_code in [1, 2, 3]:
                mock_validate.side_effect = SystemExit(exit_code)
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == exit_code
    
    def test_main_prints_error_message_on_validation_failure(self):
        """Test that main() prints helpful error message on validation failure"""
        from bot.main import main
        
        with patch('bot.main.StartupValidator.validate_all') as mock_validate, \
             patch('bot.main.ProcessManager.kill_existing'), \
             patch('bot.main.ProcessManager.write_pid'), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables'), \
             patch('bot.main.TelegramBot'), \
             patch('builtins.print') as mock_print:
            
            mock_validate.side_effect = SystemExit(1)
            
            with pytest.raises(SystemExit):
                main()
            
            # Check that error message was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            error_printed = any('ERROR' in call or 'validation failed' in call.lower() 
                              for call in print_calls)
            assert error_printed, f"No error message found in: {print_calls}"


class TestMainValidationOrder:
    """Test the order of operations in main.py"""
    
    def test_validation_is_first_operation(self):
        """Test that validation is the very first operation after print"""
        from bot.main import main
        
        operations = []
        
        def track_operation(name):
            def wrapper(*args, **kwargs):
                operations.append(name)
                if name == 'bot_run':
                    raise KeyboardInterrupt()
                if name == 'bot_init':
                    mock_instance = MagicMock()
                    mock_instance.run.side_effect = lambda: operations.append('bot_run') or (_ for _ in ()).throw(KeyboardInterrupt())
                    return mock_instance
                if name == 'kill':
                    return False
                return MagicMock()
            return wrapper
        
        with patch('bot.main.StartupValidator.validate_all', side_effect=track_operation('validate')), \
             patch('bot.main.ProcessManager.kill_existing', side_effect=track_operation('kill')), \
             patch('bot.main.ProcessManager.write_pid', side_effect=track_operation('write_pid')), \
             patch('bot.main.ProcessManager.remove_pid'), \
             patch('bot.main.create_tables', side_effect=track_operation('create_tables')), \
             patch('bot.main.TelegramBot', side_effect=track_operation('bot_init')):
            
            try:
                main()
            except KeyboardInterrupt:
                pass
            
            # Validation should be first
            assert operations[0] == 'validate'
            # Followed by kill, write_pid, create_tables, bot_init, bot_run
            assert operations == ['validate', 'kill', 'write_pid', 'create_tables', 'bot_init', 'bot_run']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
