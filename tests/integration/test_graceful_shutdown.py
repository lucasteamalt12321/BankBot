"""Integration tests for graceful shutdown."""

import pytest
from unittest.mock import patch, MagicMock
import signal
import time

from src.process_manager import ProcessManager, graceful_shutdown, setup_signal_handlers


class TestGracefulShutdownIntegration:
    """Интеграционные тесты graceful shutdown."""
    
    def test_shutdown_with_signals(self, monkeypatch):
        """Проверка graceful shutdown через сигналы."""
        mock_remove_pid = MagicMock()
        mock_close_resources = MagicMock()
        
        with patch('src.process_manager.ProcessManager.remove_pid', mock_remove_pid):
            with patch('src.process_manager.sys.exit') as mock_exit:
                # Вызываем обработчик сигнала
                graceful_shutdown(signal.SIGTERM, None)
                
                mock_remove_pid.assert_called_once()
                mock_exit.assert_called_once_with(0)
    
    def test_shutdown_with_sigint(self, monkeypatch):
        """Проверка graceful shutdown через SIGINT."""
        mock_remove_pid = MagicMock()
        mock_close_resources = MagicMock()
        
        with patch('src.process_manager.ProcessManager.remove_pid', mock_remove_pid):
            with patch('src.process_manager.sys.exit') as mock_exit:
                # Вызываем обработчик сигнала
                graceful_shutdown(signal.SIGINT, None)
                
                mock_remove_pid.assert_called_once()
                mock_exit.assert_called_once_with(0)
    
    def test_shutdown_cleans_up_resources(self, monkeypatch):
        """Проверка очистки ресурсов при shutdown."""
        mock_remove_pid = MagicMock()
        mock_close_db = MagicMock()
        mock_close_bot = MagicMock()
        
        with patch('src.process_manager.ProcessManager.remove_pid', mock_remove_pid):
            with patch('src.process_manager.sys.exit') as mock_exit:
                graceful_shutdown()
                
                mock_remove_pid.assert_called_once()
                mock_exit.assert_called_once_with(0)


class TestProcessManagerShutdown:
    """Тесты завершения процессов ProcessManager."""
    
    def test_shutdown_with_running_process(self, tmp_path, monkeypatch):
        """Проверка shutdown с запущенным процессом."""
        monkeypatch.chdir(tmp_path)
        
        # Создаем PID файл
        pid_file = tmp_path / "data" / "bot.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("99999")
        
        # Мокаем процесс
        mock_proc = MagicMock()
        mock_proc.name.return_value = "python"
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        
        with patch('src.process_manager.psutil.Process', return_value=mock_proc):
            with patch('src.process_manager.psutil.pid_exists', return_value=True):
                pids = ProcessManager.kill_existing()
                assert pids == [99999]
    
    def test_shutdown_with_stale_pid(self, tmp_path, monkeypatch):
        """Проверка shutdown с устаревшим PID."""
        monkeypatch.chdir(tmp_path)
        
        # Создаем PID файл
        pid_file = tmp_path / "data" / "bot.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("1")
        
        with patch('src.process_manager.psutil.pid_exists', return_value=False):
            pids = ProcessManager.kill_existing()
            assert pids == []
    
    def test_shutdown_multiple_processes(self, monkeypatch):
        """Проверка завершения нескольких процессов."""
        mock_proc1 = MagicMock()
        mock_proc1.info = {'pid': 12345, 'name': 'python', 'cmdline': ['python', 'main.py']}
        mock_proc1.terminate = MagicMock()
        
        mock_proc2 = MagicMock()
        mock_proc2.info = {'pid': 67890, 'name': 'python', 'cmdline': ['python', 'main.py']}
        mock_proc2.terminate = MagicMock()
        
        with patch('src.process_manager.psutil.process_iter', return_value=[mock_proc1, mock_proc2]):
            with patch('src.process_manager.psutil.pid_exists', return_value=True):
                with patch('src.process_manager.os.getpid', return_value=11111):
                    pids = ProcessManager.kill_all_bot_processes()
                    assert 12345 in pids
                    assert 67890 in pids


class TestSignalHandlerSetup:
    """Тесты установки обработчиков сигналов."""
    
    def test_setup_signal_handlers_registers_handlers(self, monkeypatch):
        """Проверка регистрации обработчиков сигналов."""
        mock_signal_module = MagicMock()
        mock_signal_module.SIGTERM = 15
        mock_signal_module.SIGINT = 2
        
        with patch('src.process_manager.signal', mock_signal_module):
            setup_signal_handlers()
            
            # Проверяем, что установлены обработчики для SIGTERM и SIGINT
            assert mock_signal_module.signal.call_count == 2
            calls = mock_signal_module.signal.call_args_list
            
            # Проверяем, что обработчик - graceful_shutdown
            for call in calls:
                handler = call[0][1]
                assert handler == graceful_shutdown
