"""Unit tests for ProcessManager."""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path
import os
import signal

from src.process_manager import ProcessManager, graceful_shutdown, setup_signal_handlers


class TestProcessManagerPID:
    """Тесты управления PID файлами."""
    
    def test_write_pid(self, tmp_path, monkeypatch):
        """Проверка записи PID файла."""
        monkeypatch.chdir(tmp_path)
        
        ProcessManager.write_pid()
        
        pid_file = tmp_path / "data" / "bot.pid"
        assert pid_file.exists()
        assert int(pid_file.read_text()) == os.getpid()
    
    def test_read_pid(self, tmp_path, monkeypatch):
        """Проверка чтения PID файла."""
        monkeypatch.chdir(tmp_path)
        
        # Создаем PID файл
        pid_file = tmp_path / "data" / "bot.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))
        
        pid = ProcessManager.read_pid()
        assert pid == os.getpid()
    
    def test_read_pid_not_exists(self, tmp_path, monkeypatch):
        """Проверка чтения несуществующего PID файла."""
        monkeypatch.chdir(tmp_path)
        
        pid = ProcessManager.read_pid()
        assert pid is None
    
    def test_remove_pid(self, tmp_path, monkeypatch):
        """Проверка удаления PID файла."""
        monkeypatch.chdir(tmp_path)
        
        # Создаем PID файл
        pid_file = tmp_path / "data" / "bot.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))
        
        ProcessManager.remove_pid()
        assert not pid_file.exists()
    
    def test_remove_pid_not_exists(self, tmp_path, monkeypatch):
        """Проверка удаления несуществующего PID файла."""
        monkeypatch.chdir(tmp_path)
        
        # Не должно вызывать ошибку
        ProcessManager.remove_pid()


class TestProcessManagerKill:
    """Тесты завершения процессов."""
    
    def test_kill_existing_success(self, tmp_path, monkeypatch):
        """Проверка успешного завершения существующего процесса."""
        monkeypatch.chdir(tmp_path)
        
        # Создаем PID файл
        pid_file = tmp_path / "data" / "bot.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("12345")
        
        # Мокаем существующий процесс
        mock_proc = MagicMock()
        mock_proc.name.return_value = "python"
        mock_proc.terminate = MagicMock()
        mock_proc.wait = MagicMock()
        
        with patch('src.process_manager.psutil.Process', return_value=mock_proc):
            with patch('src.process_manager.psutil.pid_exists', return_value=True):
                pids = ProcessManager.kill_existing()
                assert pids == [12345]
    
    def test_kill_existing_not_exists(self, tmp_path, monkeypatch):
        """Проверка завершения несуществующего процесса."""
        monkeypatch.chdir(tmp_path)
        
        # Создаем PID файл
        pid_file = tmp_path / "data" / "bot.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("99999")
        
        with patch('src.process_manager.psutil.pid_exists', return_value=False):
            pids = ProcessManager.kill_existing()
            assert pids == []
    
    def test_kill_existing_no_pid_file(self, tmp_path, monkeypatch):
        """Проверка завершения без PID файла."""
        monkeypatch.chdir(tmp_path)
        
        pids = ProcessManager.kill_existing()
        assert pids == []
    
    def test_get_running_pids(self, monkeypatch):
        """Проверка получения запущенных PID."""
        mock_proc1 = MagicMock()
        mock_proc1.info = {'pid': 12345, 'name': 'python', 'cmdline': ['python', 'main.py']}
        
        mock_proc2 = MagicMock()
        mock_proc2.info = {'pid': 67890, 'name': 'node', 'cmdline': ['node', 'server.js']}
        
        with patch('src.process_manager.psutil.process_iter', return_value=[mock_proc1, mock_proc2]):
            pids = ProcessManager.get_running_pids()
            assert 12345 in pids
            assert 67890 not in pids
    
    def test_kill_all_bot_processes(self, monkeypatch):
        """Проверка завершения всех процессов бота."""
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


class TestGracefulShutdown:
    """Тесты graceful shutdown."""
    
    def test_graceful_shutdown(self, monkeypatch):
        """Проверка graceful shutdown."""
        mock_remove_pid = MagicMock()
        
        with patch('src.process_manager.ProcessManager.remove_pid', mock_remove_pid):
            with patch('src.process_manager.sys.exit') as mock_exit:
                graceful_shutdown(signal.SIGTERM, None)
                mock_remove_pid.assert_called_once()
                mock_exit.assert_called_once_with(0)
    
    def test_graceful_shutdown_called_directly(self, monkeypatch):
        """Проверка вызова graceful_shutdown напрямую."""
        mock_remove_pid = MagicMock()
        
        with patch('src.process_manager.ProcessManager.remove_pid', mock_remove_pid):
            with patch('src.process_manager.sys.exit') as mock_exit:
                graceful_shutdown()
                mock_remove_pid.assert_called_once()
                mock_exit.assert_called_once_with(0)


class TestSignalHandlers:
    """Тесты установки обработчиков сигналов."""
    
    def test_setup_signal_handlers(self, monkeypatch):
        """Проверка установки обработчиков сигналов."""
        mock_signal_module = MagicMock()
        mock_signal_module.SIGTERM = 15
        mock_signal_module.SIGINT = 2
        
        with patch('src.process_manager.signal', mock_signal_module):
            setup_signal_handlers()
            assert mock_signal_module.signal.call_count == 2
            # Проверяем, что установлены SIGTERM и SIGINT
            calls = mock_signal_module.signal.call_args_list
            signal_names = [call[0][0] for call in calls]
            assert 15 in signal_names
            assert 2 in signal_names
