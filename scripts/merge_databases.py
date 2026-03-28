#!/usr/bin/env python3
"""
Скрипт для объединения баз данных bot.db
Объединяет данные из нескольких БД в одну основную
"""
import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path


def get_db_info(db_path):
    """Получить информацию о базе данных"""
    if not os.path.exists(db_path):
        return None
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    info = {
        'path': db_path,
        'size': os.path.getsize(db_path),
        'modified': datetime.fromtimestamp(os.path.getmtime(db_path)),
        'tables': []
    }
    
    # Получить список таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")  # noqa: S608 - table name from sqlite_master, not user input
        count = cursor.fetchone()[0]
        info['tables'].append({'name': table_name, 'rows': count})
    
    conn.close()
    return info


def backup_database(db_path):
    """Создать резервную копию базы данных"""
    if not os.path.exists(db_path):
        return None
    
    backup_dir = Path('backups')
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f"bot_backup_{timestamp}.db"
    
    shutil.copy2(db_path, backup_path)
    print(f"✓ Создана резервная копия: {backup_path}")
    return backup_path


def merge_databases(source_db, target_db):
    """Объединить данные из source_db в target_db"""
    if not os.path.exists(source_db):
        print(f"✗ Источник не найден: {source_db}")
        return False
    
    if not os.path.exists(target_db):
        print(f"✗ Целевая БД не найдена: {target_db}")
        return False
    
    print(f"\nОбъединение {source_db} -> {target_db}")
    
    # Подключиться к целевой БД
    target_conn = sqlite3.connect(target_db)
    target_cursor = target_conn.cursor()
    
    # Присоединить исходную БД
    # noqa: S608 - source_db is a validated file path, not user-controlled SQL
    target_cursor.execute(f"ATTACH DATABASE '{source_db}' AS source")  # noqa: S608
    
    # Получить список таблиц из исходной БД
    target_cursor.execute("SELECT name FROM source.sqlite_master WHERE type='table'")
    tables = [row[0] for row in target_cursor.fetchall()]
    
    merged_count = 0
    
    for table in tables:
        try:
            # Проверить, существует ли таблица в целевой БД
            target_cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            )
            table_exists = target_cursor.fetchone() is not None
            
            if table_exists:
                # Получить структуру таблицы
                # Table name from sqlite_master (system source), not user input
                target_cursor.execute(f"PRAGMA table_info({table})")  # noqa: S608
                columns = [row[1] for row in target_cursor.fetchall()]
                columns_str = ', '.join(columns)
                
                # Table/column names from sqlite_master, not user input
                target_cursor.execute(
                    f"INSERT OR IGNORE INTO {table} ({columns_str}) "  # noqa: S608
                    f"SELECT {columns_str} FROM source.{table}"
                )
                
                rows_added = target_cursor.rowcount
                if rows_added > 0:
                    print(f"  ✓ {table}: добавлено {rows_added} записей")
                    merged_count += rows_added
                else:
                    print(f"  - {table}: нет новых записей")
            else:
                print(f"  ! {table}: таблица не существует в целевой БД, пропущено")
        
        except sqlite3.Error as e:
            print(f"  ✗ {table}: ошибка - {e}")
    
    target_cursor.execute("DETACH DATABASE source")
    target_conn.commit()
    target_conn.close()
    
    print(f"\nВсего объединено записей: {merged_count}")
    return True


def main():
    """Основная функция"""
    print("=" * 60)
    print("Скрипт объединения баз данных bot.db")
    print("=" * 60)
    
    # Найти все bot.db файлы
    root_db = Path('bot.db')
    data_db = Path('data/bot.db')
    
    databases = []
    if root_db.exists():
        databases.append(root_db)
    if data_db.exists():
        databases.append(data_db)
    
    if not databases:
        print("\n✗ Не найдено ни одной базы данных bot.db")
        return
    
    print(f"\nНайдено баз данных: {len(databases)}")
    print()
    
    # Показать информацию о каждой БД
    db_infos = []
    for db_path in databases:
        info = get_db_info(str(db_path))
        if info:
            db_infos.append(info)
            print(f"📁 {db_path}")
            print(f"   Размер: {info['size']:,} байт")
            print(f"   Изменена: {info['modified']}")
            print("   Таблицы:")
            for table in info['tables']:
                print(f"     - {table['name']}: {table['rows']} записей")
            print()
    
    if len(db_infos) < 2:
        print("✓ Найдена только одна база данных, объединение не требуется")
        return
    
    # Определить основную БД (с наибольшим количеством данных)
    main_db = max(db_infos, key=lambda x: sum(t['rows'] for t in x['tables']))
    other_dbs = [db for db in db_infos if db != main_db]
    
    print(f"Основная БД: {main_db['path']}")
    print(f"Объединяемые БД: {[db['path'] for db in other_dbs]}")
    print()
    
    # Создать резервные копии
    print("Создание резервных копий...")
    for db_info in db_infos:
        backup_database(db_info['path'])
    print()
    
    # Объединить данные
    for db_info in other_dbs:
        merge_databases(db_info['path'], main_db['path'])
    
    print("\n" + "=" * 60)
    print("Объединение завершено!")
    print("=" * 60)
    
    # Показать итоговую информацию
    final_info = get_db_info(main_db['path'])
    print(f"\nИтоговая база данных: {main_db['path']}")
    print("Таблицы:")
    for table in final_info['tables']:
        print(f"  - {table['name']}: {table['rows']} записей")
    
    print("\nРекомендации:")
    for db_info in other_dbs:
        print(f"  - Удалите или переместите: {db_info['path']}")
    print(f"  - Используйте основную БД: {main_db['path']}")


if __name__ == '__main__':
    main()
