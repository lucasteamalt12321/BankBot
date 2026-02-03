#!/usr/bin/env python3
"""
Тест исправлений AdminSystem
"""
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.admin_system import AdminSystem

def test_admin_system():
    """Тестируем AdminSystem с исправлениями"""
    
    print("=== Тест AdminSystem ===")
    
    # Инициализируем систему с тестовой базой данных
    admin_system = AdminSystem('test_bot.db')
    
    # Тестовый пользователь
    test_user_id = 2091908459  # LucasTeamLuke
    
    print(f"1. Проверяем пользователя {test_user_id}...")
    user = admin_system.get_user_by_id(test_user_id)
    if user:
        print(f"   Найден: {user}")
    else:
        print("   Не найден, регистрируем...")
        success = admin_system.register_user(test_user_id, "LucasTeamLuke", "LucasTeam")
        if success:
            print("   Регистрация успешна")
            user = admin_system.get_user_by_id(test_user_id)
            print(f"   Пользователь после регистрации: {user}")
        else:
            print("   Ошибка регистрации")
            return False
    
    print(f"2. Проверяем права администратора...")
    is_admin_before = admin_system.is_admin(test_user_id)
    print(f"   Администратор до установки прав: {is_admin_before}")
    
    print(f"3. Устанавливаем права администратора...")
    success = admin_system.set_admin_status(test_user_id, True)
    if success:
        print("   Права установлены успешно")
    else:
        print("   Ошибка установки прав")
    
    print(f"4. Проверяем права администратора после установки...")
    is_admin_after = admin_system.is_admin(test_user_id)
    print(f"   Администратор после установки прав: {is_admin_after}")
    
    print(f"5. Получаем пользователя еще раз...")
    user_final = admin_system.get_user_by_id(test_user_id)
    if user_final:
        print(f"   Финальные данные: {user_final}")
    else:
        print("   Пользователь не найден!")
        return False
    
    print("=== Тест завершен успешно ===")
    return True

if __name__ == "__main__":
    success = test_admin_system()
    sys.exit(0 if success else 1)