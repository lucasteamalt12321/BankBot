#!/usr/bin/env python3
"""
Тест команды /profile для проверки работоспособности
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import get_db
from utils.admin.admin_system import AdminSystem
from src.config import settings

def test_profile_command():
    """Тестируем команду profile"""
    print("[TEST] Тестирование команды /profile...")
    
    # Инициализируем админ систему
    admin_system = AdminSystem("data/bot.db")
    
    # Тестовый пользователь
    test_user_id = settings.ADMIN_TELEGRAM_ID  # LucasTeamLuke
    
    print(f"[TEST] Проверяем пользователя {test_user_id}...")
    
    # Получаем пользователя
    user = admin_system.get_user_by_id(test_user_id)
    
    if user:
        print(f"[SUCCESS] Пользователь найден:")
        print(f"  - ID: {user['telegram_id']}")
        print(f"  - Имя: {user['first_name']}")
        print(f"  - Username: {user['username']}")
        print(f"  - Баланс: {user['balance']}")
        print(f"  - Админ: {user['is_admin']}")
    else:
        print(f"[ERROR] Пользователь не найден!")
        print(f"[INFO] Попытка регистрации...")
        
        success = admin_system.register_user(
            test_user_id,
            "LucasTeamLuke",
            "Lucas"
        )
        
        if success:
            print(f"[SUCCESS] Пользователь зарегистрирован!")
            
            # Устанавливаем права администратора
            admin_system.set_admin_status(test_user_id, True)
            print(f"[SUCCESS] Права администратора установлены!")
            
            # Проверяем снова
            user = admin_system.get_user_by_id(test_user_id)
            if user:
                print(f"[SUCCESS] Пользователь найден после регистрации:")
                print(f"  - ID: {user['telegram_id']}")
                print(f"  - Имя: {user['first_name']}")
                print(f"  - Username: {user['username']}")
                print(f"  - Баланс: {user['balance']}")
                print(f"  - Админ: {user['is_admin']}")
        else:
            print(f"[ERROR] Не удалось зарегистрировать пользователя!")
    
    print("\n[TEST] Проверяем транзакции...")
    
    # Получаем транзакции
    conn = admin_system.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (test_user_id,))
    user_row = cursor.fetchone()
    
    if user_row:
        internal_id = user_row['id']
        print(f"[INFO] Внутренний ID пользователя: {internal_id}")
        
        cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE user_id = ?", (internal_id,))
        result = cursor.fetchone()
        total_transactions = result['count'] if result else 0
        
        print(f"[INFO] Всего транзакций: {total_transactions}")
    else:
        print(f"[ERROR] Пользователь не найден в базе данных!")
    
    conn.close()
    
    print("\n[TEST] Тест завершен!")

if __name__ == "__main__":
    test_profile_command()
