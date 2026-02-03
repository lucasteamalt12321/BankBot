#!/usr/bin/env python3
"""
Тест для проверки правильности использования telegram_id
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.simple_db import register_user, get_user_by_id, update_user_balance, add_transaction, is_admin, set_admin_status
from utils.admin_system import AdminSystem

def test_telegram_id_consistency():
    """Тест консистентности использования telegram_id"""
    
    print("=== Тест консистентности telegram_id ===")
    
    # Тестовые данные
    test_telegram_id = 123456789
    test_username = "testuser"
    test_first_name = "Test User"
    
    print(f"1. Регистрируем пользователя с telegram_id: {test_telegram_id}")
    
    # Регистрируем пользователя
    success = register_user(test_telegram_id, test_username, test_first_name)
    print(f"   Результат регистрации: {success}")
    
    # Получаем пользователя по telegram_id
    user = get_user_by_id(test_telegram_id)
    print(f"2. Получили пользователя: {user}")
    
    if user:
        print(f"   telegram_id: {user.get('telegram_id')}")
        print(f"   username: {user.get('username')}")
        print(f"   balance: {user.get('balance')}")
        print(f"   is_admin: {user.get('is_admin')}")
    
    # Обновляем баланс
    print(f"3. Обновляем баланс пользователя на +100")
    new_balance = update_user_balance(test_telegram_id, 100)
    print(f"   Новый баланс: {new_balance}")
    
    # Добавляем транзакцию
    print(f"4. Добавляем транзакцию")
    transaction_id = add_transaction(test_telegram_id, 50, 'test', description="Test transaction")
    print(f"   ID транзакции: {transaction_id}")
    
    # Проверяем статус администратора
    print(f"5. Проверяем статус администратора")
    admin_status = is_admin(test_telegram_id)
    print(f"   Является администратором: {admin_status}")
    
    # Устанавливаем статус администратора
    print(f"6. Устанавливаем статус администратора")
    success = set_admin_status(test_telegram_id, True)
    print(f"   Результат установки: {success}")
    
    # Проверяем снова
    admin_status = is_admin(test_telegram_id)
    print(f"   Является администратором: {admin_status}")
    
    print("\n=== Тест AdminSystem ===")
    
    # Тестируем AdminSystem
    admin_system = AdminSystem("bot.db")
    
    # Получаем пользователя через AdminSystem
    admin_user = admin_system.get_user_by_id(test_telegram_id)
    print(f"7. AdminSystem.get_user_by_id: {admin_user}")
    
    # Обновляем баланс через AdminSystem
    new_balance = admin_system.update_balance(test_telegram_id, 25)
    print(f"8. AdminSystem.update_balance: {new_balance}")
    
    # Добавляем транзакцию через AdminSystem
    transaction_id = admin_system.add_transaction(test_telegram_id, 10, 'admin_test')
    print(f"9. AdminSystem.add_transaction: {transaction_id}")
    
    print("\n=== Тест завершен ===")

if __name__ == "__main__":
    test_telegram_id_consistency()