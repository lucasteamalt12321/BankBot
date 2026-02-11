#!/usr/bin/env python3
"""
Скрипт для пересоздания базы данных с правильной структурой
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import shutil
from datetime import datetime

def backup_database():
    """Создает резервную копию базы данных"""
    db_path = Path("data/bot.db")
    
    if not db_path.exists():
        print("ℹ️  База данных не существует, резервная копия не требуется")
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"data/bot_backup_{timestamp}.db")
    
    print(f"💾 Создание резервной копии: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"✅ Резервная копия создана")
    
    return backup_path

def recreate_database():
    """Пересоздает базу данных с правильной структурой"""
    from database.database import Base, create_engine
    from utils.core.config import settings
    
    db_path = Path("data/bot.db")
    
    # Создаем резервную копию
    backup_path = backup_database()
    
    # Удаляем старую базу данных
    if db_path.exists():
        print(f"🗑️  Удаление старой базы данных: {db_path}")
        db_path.unlink()
        print("✅ Старая база данных удалена")
    
    # Создаем новую базу данных
    print(f"🔨 Создание новой базы данных: {db_path}")
    
    # Убедимся, что папка data существует
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Создаем engine и таблицы
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    
    print("✅ Новая база данных создана со всеми таблицами")
    
    # Проверяем структуру
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print(f"\n📋 Созданные таблицы ({len(tables)}):")
    for table in tables:
        print(f"   - {table[0]}")
    
    # Проверяем структуру таблицы users
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    
    print(f"\n📋 Колонки таблицы users ({len(columns)}):")
    for col in columns:
        col_id, name, col_type, not_null, default, pk = col
        print(f"   - {name} ({col_type})")
    
    conn.close()
    
    return backup_path

if __name__ == "__main__":
    print("=" * 70)
    print("Пересоздание базы данных")
    print("=" * 70)
    print()
    
    try:
        backup_path = recreate_database()
        
        print()
        print("=" * 70)
        print("✅ База данных успешно пересоздана")
        if backup_path:
            print(f"💾 Резервная копия сохранена: {backup_path}")
        print("=" * 70)
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ Ошибка при пересоздании базы данных: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
