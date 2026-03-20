"""Process management system for safe bot startup and shutdown."""

import os
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional
import psutil

from src.logging_config import get_logger

logger = get_logger(__name__)


class ProcessManager:
    """
    Управление процессами бота.
    
    Обеспечивает безопасный запуск и завершение процессов бота
    с использованием PID-файлов вместо поиска по имени.
    """
    
    PID_FILE = Path("data/bot.pid")
    
    @classmethod
    def write_pid(cls) -> None:
        """
        Записывает PID текущего процесса в файл.
        
        Создает директорию data/ если она не существует.
        """
        cls.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.PID_FILE.write_text(str(os.getpid()))
        logger.info(f"✅ PID записан: {os.getpid()}")
    
    @classmethod
    def read_pid(cls) -> Optional[int]:
        """
        Считывает PID из файла.
        
        Returns:
            PID процесса или None если файл не найден
        """
        if cls.PID_FILE.exists():
            try:
                pid = int(cls.PID_FILE.read_text().strip())
                logger.info(f"✅ PID считан: {pid}")
                return pid
            except (ValueError, IOError) as e:
                logger.warning(f"⚠️ Ошибка чтения PID файла: {e}")
                return None
        return None
    
    @classmethod
    def remove_pid(cls) -> None:
        """
        Удаляет PID файл.
        """
        if cls.PID_FILE.exists():
            cls.PID_FILE.unlink()
            logger.info("✅ PID файл удален")
    
    @classmethod
    def kill_existing(cls) -> List[int]:
        """
        Убивает существующий процесс бота по PID.
        
        Returns:
            Список убитых PID
        """
        pid = cls.read_pid()
        if not pid:
            logger.info("ℹ️ PID файл не найден, нет процессов для завершения")
            return []
        
        try:
            # Проверяем, существует ли процесс
            if not psutil.pid_exists(pid):
                logger.warning(f"⚠️ Процесс {pid} не найден")
                cls.remove_pid()
                return []
            
            # Получаем процесс
            proc = psutil.Process(pid)
            proc_name = proc.name()
            
            logger.info(f"📩 Отправка SIGTERM процессу {pid} ({proc_name})...")
            proc.terminate()
            
            # Ждем завершения до 5 секунд
            try:
                proc.wait(timeout=5)
                logger.info(f"✅ Процесс {pid} завершен")
            except psutil.TimeoutExpired:
                logger.warning(f"⚠️ Процесс {pid} не завершился, отправка SIGKILL...")
                proc.kill()
                proc.wait(timeout=2)
                logger.info(f"✅ Процесс {pid} принудительно завершен")
            
            cls.remove_pid()
            return [pid]
            
        except psutil.NoSuchProcess:
            logger.warning(f"⚠️ Процесс {pid} уже не существует")
            cls.remove_pid()
            return []
        except psutil.AccessDenied:
            logger.error(f"❌ Нет прав для завершения процесса {pid}")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка при завершении процесса {pid}: {e}")
            return []
    
    @classmethod
    def get_running_pids(cls) -> List[int]:
        """
        Получает список всех запущенных процессов бота.
        
        Returns:
            Список PID запущенных процессов
        """
        running_pids = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and len(cmdline) > 1:
                    cmdline_str = ' '.join(cmdline)
                    # Проверяем, содержит ли команда запуск main.py
                    if 'main.py' in cmdline_str and 'python' in cmdline_str.lower():
                        pid = proc.info['pid']
                        running_pids.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        return running_pids
    
    @classmethod
    def kill_all_bot_processes(cls) -> List[int]:
        """
        Убивает все процессы, связанные с ботом.
        
        Returns:
            Список убитых PID
        """
        current_pid = os.getpid()
        killed_pids = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and len(cmdline) > 1:
                    cmdline_str = ' '.join(cmdline)
                    if 'main.py' in cmdline_str and 'python' in cmdline_str.lower():
                        pid = proc.info['pid']
                        if pid != current_pid:
                            logger.info(f"📩 Отправка SIGTERM процессу {pid}...")
                            proc.terminate()
                            killed_pids.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Ждем завершения
        time.sleep(1)
        
        # Принудительное завершение оставшихся
        for pid in killed_pids:
            try:
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    proc.kill()
                    logger.info(f"✅ Принудительно завершен процесс {pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return killed_pids


def graceful_shutdown(signum=None, frame=None):
    """
    Graceful shutdown handler.
    
    Can be used as a signal handler or called directly.
    """
    logger.info(f"Received signal {signum}, initiating shutdown...")
    
    # Remove PID file
    ProcessManager.remove_pid()
    
    # Exit gracefully
    sys.exit(0)


def setup_signal_handlers():
    """
    Устанавливает обработчики сигналов для graceful shutdown.
    """
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, graceful_shutdown)
    logger.info("✅ Обработчики сигналов установлены")
