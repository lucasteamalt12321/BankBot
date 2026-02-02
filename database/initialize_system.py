#!/usr/bin/env python3
"""
Скрипт инициализации системы
"""
import os
import sys
from datetime import datetime
from sqlalchemy.orm import Session

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import create_tables, get_db
from config import settings
from bank_system import BankSystem
from shop_system import EnhancedShopSystem
from achievements import AchievementSystem
from user_manager import UserManager
from games_system import GamesSystem
from dnd_system import DndSystem
from motivation_system import MotivationSystem
from social_system import SocialSystem
from notification_system import NotificationSystem
from monitoring_system import MonitoringSystem, AlertSystem
from backup_system import BackupSystem
from error_handling import ErrorHandlingSystem
import structlog

logger = structlog.get_logger()


def initialize_system():
    """Инициализация всей системы"""
    print("[INIT] Начало инициализации системы...")
    
    # Создаем таблицы базы данных
    print("[DB] Создание таблиц базы данных...")
    create_tables()
    print("[DB] Таблицы созданы успешно")
    
    # Инициализируем системы
    db = next(get_db())
    try:
        print("[SYSTEM] Инициализация банковской системы...")
        bank_system = BankSystem(db)
        
        print("[SYSTEM] Инициализация магазина...")
        shop_system = EnhancedShopSystem(db)
        shop_system.initialize_default_categories()
        shop_system.initialize_default_items()
        print("[SHOP] Категории и товары инициализированы")
        
        print("[SYSTEM] Инициализация системы достижений...")
        achievement_system = AchievementSystem(db)
        print("[ACHIEVEMENTS] Система достижений инициализирована")
        
        print("[SYSTEM] Инициализация системы мотивации...")
        motivation_system = MotivationSystem(db)
        print("[MOTIVATION] Система мотивации инициализирована")
        
        print("[SYSTEM] Инициализация D&D системы...")
        dnd_system = DndSystem(db)
        print("[DND] D&D система инициализирована")
        
        print("[SYSTEM] Инициализация игровой системы...")
        games_system = GamesSystem(db)
        print("[GAMES] Игровая система инициализирована")
        
        print("[SYSTEM] Инициализация социальной системы...")
        social_system = SocialSystem(db)
        print("[SOCIAL] Социальная система инициализирована")
        
        print("[SYSTEM] Инициализация системы уведомлений...")
        notification_system = NotificationSystem(db)
        print("[NOTIFICATIONS] Система уведомлений инициализирована")
        
        print("[SYSTEM] Инициализация системы мониторинга...")
        monitoring_system = MonitoringSystem(db)
        alert_system = AlertSystem(monitoring_system)
        print("[MONITORING] Система мониторинга и алертов инициализирована")
        
        print("[SYSTEM] Инициализация системы бэкапов...")
        backup_system = BackupSystem()
        print("[BACKUP] Система резервного копирования инициализирована")
        
        print("[SYSTEM] Инициализация системы обработки ошибок...")
        error_handling_system = ErrorHandlingSystem(db)
        print("[ERROR] Система обработки ошибок инициализирована")
        
        print("[SYSTEM] Инициализация менеджера пользователей...")
        user_manager = UserManager(db)
        print("[USERS] Менеджер пользователей инициализирован")
        
        # Проверяем систему
        print("[CHECK] Выполнение проверки системы...")
        business_metrics = monitoring_system.get_business_metrics()
        system_health = monitoring_system.get_system_health()
        performance_metrics = monitoring_system.check_performance_metrics()
        
        print(f"[CHECK] Метрики бизнеса: {business_metrics}")
        print(f"[CHECK] Здоровье системы: CPU {system_health['cpu']['percent']}%, Memory {system_health['memory']['percent']}%")
        print(f"[CHECK] Метрики производительности: {performance_metrics}")
        
        # Проверяем алерты
        alerts = alert_system.check_and_send_alerts()
        active_alerts = alert_system.get_active_alerts()
        print(f"[CHECK] Активные алерты: {len(active_alerts)}")
        
        print("[SUCCESS] Система успешно инициализирована!")
        
        # Выводим статистику
        print("\n[STATS] Статистика системы:")
        print(f"  - Всего пользователей: {business_metrics['total_users']}")
        print(f"  - Транзакций сегодня: {business_metrics['today_transactions']}")
        print(f"  - Активных пользователей сегодня: {business_metrics['active_users_today']}")
        print(f"  - Средний баланс: {business_metrics['average_balance']}")
        
    except Exception as e:
        print(f"[ERROR] Ошибка при инициализации системы: {e}")
        logger.error("System initialization failed", error=str(e))
        raise
    finally:
        db.close()


def main():
    """Основная функция запуска"""
    print("[START] Запуск инициализации системы...")
    print(f"[CONFIG] База данных: {settings.database_url}")
    print(f"[CONFIG] Токен бота: {'***' if settings.bot_token else 'НЕ НАЙДЕН'}")
    print(f"[CONFIG] Администраторы: {settings.admin_user_ids}")
    
    try:
        initialize_system()
        print(f"\n[SUCCESS] Инициализация завершена успешно в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"\n[FAILURE] Инициализация завершена с ошибкой: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()