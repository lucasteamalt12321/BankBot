#!/usr/bin/env python3
# main.py - основной файл запуска Telegram-бота банк-аггрегатора LucasTeam

import os
import sys
import structlog
import psutil
import time
import asyncio
from typing import Optional

from bot.bot import TelegramBot
from database.database import create_tables
from src.startup_validator import validate_startup
from src.process_manager import ProcessManager

logger = structlog.get_logger()


class BotApplication:
    """Wrapper for Telegram bot with graceful shutdown support.
    
    Provides unified interface for bot lifecycle management including:
    - Database connection management
    - Background task cleanup
    - Bot application shutdown
    - PID file management
    """
    
    def __init__(self):
        self.bot: Optional[TelegramBot] = None
    
    async def shutdown(self) -> bool:
        """Perform graceful shutdown of all resources.
        
        Shuts down in order:
        1. Database connections (engine.dispose)
        2. Background tasks
        3. Bot application
        4. PID file
        
        Each step is isolated - errors in one step don't stop others.
        PID file is always removed, even if other steps fail.
        
        Returns:
            bool: True if all resources cleaned up successfully
        """
        logger.info("Starting graceful shutdown", bot_running=self.bot is not None)
        
        errors = []
        
        # Step 1: Close database
        try:
            logger.info("Shutting down database connections")
            import database.database
            database.database.engine.dispose()
        except Exception as e:
            errors.append(f"database: {e}")
            logger.error("Database shutdown failed", error=str(e))
        
        # Step 2: Stop background tasks
        if self.bot is not None:
            try:
                if hasattr(self.bot, 'background_task_manager'):
                    btm = self.bot.background_task_manager
                    if btm is not None and hasattr(btm, 'stop_periodic_cleanup'):
                        logger.info("Stopping background tasks")
                        if asyncio.iscoroutinefunction(btm.stop_periodic_cleanup):
                            await btm.stop_periodic_cleanup()
                        else:
                            btm.stop_periodic_cleanup()
            except Exception as e:
                errors.append(f"background_tasks: {e}")
                logger.error("Background task shutdown failed", error=str(e))
        
        # Step 3: Stop bot application
        if self.bot is not None:
            try:
                if hasattr(self.bot, 'application'):
                    app = self.bot.application
                    if app is not None:
                        if hasattr(app, 'running') and not app.running:
                            logger.info("Bot application already stopped")
                        else:
                            logger.info("Stopping bot application")
                            await app.stop()
            except Exception as e:
                errors.append(f"bot_application: {e}")
                logger.error("Bot application shutdown failed", error=str(e))
        
        # Step 4: Always remove PID file (even on errors)
        try:
            logger.info("Removing PID file")
            ProcessManager.remove_pid()
        except Exception as e:
            errors.append(f"pid_file: {e}")
            logger.error("PID file removal failed", error=str(e))
        
        if errors:
            logger.info("Shutdown completed with errors", errors=errors)
            return False
        
        logger.info("Shutdown completed successfully")
        return True

def kill_existing_bot_processes():
    """Убивает все существующие процессы, связанные с ботом"""
    current_pid = os.getpid()
    killed_processes = []
    
    print(f"[KILL] Поиск старых процессов бота (текущий PID: {current_pid})...")
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Получаем командную строку процесса
            cmdline = proc.info['cmdline']
            if cmdline and len(cmdline) > 1:  # Убедимся, что есть хотя бы exe и аргумент
                cmdline_str = ' '.join(cmdline)
                # Проверяем, содержит ли команда запуск main.py
                if 'main.py' in cmdline_str and 'python' in cmdline_str.lower():
                    pid = proc.info['pid']
                    if pid != current_pid:
                        print(f"[KILL] Найден старый процесс бота с PID {pid}, убиваю...")
                        proc.terminate() # Плавное завершение
                        killed_processes.append((pid, proc))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    # Ждем завершения процессов или убиваем жестко (асинхронно)
    for pid, proc in killed_processes:
        try:
            # Не ждем завершения процесса синхронно, просто помечаем для убийства
            print(f"[KILL] Помечен процесс {pid} для завершения")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"[KILL] Процесс {pid} уже не существует или нет доступа")
    
    # Краткая пауза для завершения, но не ждем долго
    time.sleep(1)
    
    if killed_processes:
        print(f"[KILL] Убито {len(killed_processes)} старых процессов бота")
        time.sleep(2)  # Даем время для полного завершения
    else:
        print("[KILL] Старые процессы бота не найдены")

def main():
    """Основная функция запуска бота"""
    
    print("[START] Запуск Telegram-бота банк-аггрегатора LucasTeam...")
    
    # Валидация конфигурации перед запуском
    print("[VALIDATE] Проверка конфигурации...")
    if not validate_startup():
        print("[ERROR] Валидация конфигурации не пройдена. Остановка бота.")
        sys.exit(1)
    print("[VALIDATE] Конфигурация валидна")
    
    # Убиваем старые процессы перед запуском
    kill_existing_bot_processes()
    
    print("[INFO] Бот запускается с настройками и расширенным функционалом")
    print("[GAMES] Поддерживаемые игры: Shmalala, GD Cards, True Mafia, Bunker RP")
    print("[CURRENCY] Настроена система конвертации валюты из разных источников")
    print("[SHOP] Загружен магазин товаров и привилегий")
    print("[BONUSES] Активированы ежедневные бонусы и задания")
    print("[ADMIN] Доступны административные команды")
    
    # Создаем таблицы БД при запуске
    create_tables()
    
    # Создаем и запускаем бота
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    # Bridge-модуль запускается отдельно через bot/bridge/main_bridge.py (aiogram)
    # Текущий main.py использует python-telegram-bot для основного функционала
    main()