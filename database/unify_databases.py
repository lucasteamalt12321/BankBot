"""
Скрипт для объединения всех баз данных в одну: data/bot.db
Удаляет дублирующиеся БД из корня
"""

import os
import sqlite3
import shutil
from pathlib import Path

def unify_databases():
    """Объединяет все базы данных в data/bot.db"""
    
    root_dir = Path(__file__).parent.parent
    data_dir = root_dir / "data"
    
    # Создаем папку data если её нет
    data_dir.mkdir(exist_ok=True)
    
    # Целевая БД
    target_db = data_dir / "bot.db"
    
    # Список БД для объединения
    databases_to_merge = [
        root_dir / "bot.db",
        root_dir / "admin_system.db"
    ]
    
    print("=" * 60)
    print("ОБЪЕДИНЕНИЕ БАЗ ДАННЫХ")
    print("=" * 60)
    
    # Если целевая БД не существует, создаем её из первой найденной
    if not target_db.exists():
        for db_path in databases_to_merge:
            if db_path.exists():
                print(f"\n✓ Копирую {db_path.name} -> data/bot.db")
                shutil.copy2(db_path, target_db)
                break
    
    # Проверяем структуру целевой БД
    if target_db.exists():
        print(f"\n✓ Целевая БД существует: {target_db}")
        
        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()
        
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"  Таблицы: {', '.join(tables)}")
        
        # Проверяем наличие важных полей
        if 'users' in tables:
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"  Поля users: {', '.join(columns)}")
            
            # Добавляем is_admin если его нет
            if 'is_admin' not in columns:
                print("  ⚠ Добавляю поле is_admin...")
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
                conn.commit()
                print("  ✓ Поле is_admin добавлено")
        
        conn.close()
    
    # Удаляем дублирующиеся БД из корня
    print("\n" + "=" * 60)
    print("ОЧИСТКА ДУБЛИРУЮЩИХСЯ БД")
    print("=" * 60)
    
    for db_path in databases_to_merge:
        if db_path.exists() and db_path != target_db:
            print(f"\n✓ Удаляю {db_path.name} из корня")
            db_path.unlink()
    
    # Проверяем финальное состояние
    print("\n" + "=" * 60)
    print("ФИНАЛЬНОЕ СОСТОЯНИЕ")
    print("=" * 60)
    
    print(f"\n✓ Основная БД: data/bot.db")
    
    if target_db.exists():
        size = target_db.stat().st_size
        print(f"  Размер: {size:,} байт")
        
        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()
        
        # Считаем пользователей
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            users_count = cursor.fetchone()[0]
            print(f"  Пользователей: {users_count}")
        except:
            print("  Пользователей: 0 (таблица не создана)")
        
        conn.close()
    
    print("\n" + "=" * 60)
    print("✅ ОБЪЕДИНЕНИЕ ЗАВЕРШЕНО")
    print("=" * 60)
    print("\nВсе модули теперь должны использовать: data/bot.db")
    print("Проверьте конфигурацию в:")
    print("  - utils/admin/admin_system.py")
    print("  - bot/bot.py")
    print("  - database/database.py")


if __name__ == "__main__":
    unify_databases()
