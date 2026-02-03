import sqlite3
from datetime import datetime

def test_database_operations():
    """Тест операций с базой данных напрямую"""
    
    conn = sqlite3.connect('bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== Тест операций с базой данных ===")
    
    # Тестовые данные
    test_telegram_id = 999888777
    test_username = "test_user_fix"
    test_first_name = "Test Fix User"
    
    try:
        # 1. Удаляем тестового пользователя если существует
        cursor.execute("DELETE FROM users WHERE telegram_id = ?", (test_telegram_id,))
        
        # 2. Создаем тестового пользователя
        print(f"1. Создаем пользователя с telegram_id: {test_telegram_id}")
        cursor.execute('''
            INSERT INTO users (telegram_id, username, first_name, balance, is_admin, created_at, last_activity)
            VALUES (?, ?, ?, 0, FALSE, ?, ?)
        ''', (test_telegram_id, test_username, test_first_name, datetime.now(), datetime.now()))
        
        # 3. Получаем внутренний ID пользователя
        cursor.execute("SELECT id, telegram_id, username, balance FROM users WHERE telegram_id = ?", (test_telegram_id,))
        user = cursor.fetchone()
        print(f"   Создан пользователь: ID={user['id']}, Telegram_ID={user['telegram_id']}, Username={user['username']}")
        
        internal_id = user['id']
        
        # 4. Обновляем баланс
        print(f"2. Обновляем баланс пользователя")
        cursor.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (100, test_telegram_id))
        
        # 5. Добавляем транзакцию (используя внутренний ID)
        print(f"3. Добавляем транзакцию")
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, transaction_type, description, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (internal_id, 100, 'test', 'Test transaction', datetime.now()))
        
        # 6. Проверяем результат
        cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (test_telegram_id,))
        balance = cursor.fetchone()['balance']
        print(f"   Новый баланс: {balance}")
        
        cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE user_id = ?", (internal_id,))
        tx_count = cursor.fetchone()['count']
        print(f"   Количество транзакций: {tx_count}")
        
        # 7. Устанавливаем статус администратора
        print(f"4. Устанавливаем статус администратора")
        cursor.execute("UPDATE users SET is_admin = TRUE WHERE telegram_id = ?", (test_telegram_id,))
        
        cursor.execute("SELECT is_admin FROM users WHERE telegram_id = ?", (test_telegram_id,))
        is_admin = cursor.fetchone()['is_admin']
        print(f"   Статус администратора: {bool(is_admin)}")
        
        conn.commit()
        print("\n✅ Все операции выполнены успешно!")
        
        # 8. Показываем итоговое состояние
        print(f"\n=== Итоговое состояние пользователя ===")
        cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (test_telegram_id,))
        final_user = cursor.fetchone()
        print(f"ID: {final_user['id']}")
        print(f"Telegram ID: {final_user['telegram_id']}")
        print(f"Username: {final_user['username']}")
        print(f"First Name: {final_user['first_name']}")
        print(f"Balance: {final_user['balance']}")
        print(f"Is Admin: {bool(final_user['is_admin'])}")
        
        # 9. Показываем транзакции
        print(f"\n=== Транзакции пользователя ===")
        cursor.execute("SELECT * FROM transactions WHERE user_id = ?", (internal_id,))
        transactions = cursor.fetchall()
        for tx in transactions:
            print(f"ID: {tx['id']}, Amount: {tx['amount']}, Type: {tx['transaction_type']}, Desc: {tx['description']}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    test_database_operations()