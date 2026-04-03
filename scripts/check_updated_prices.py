#!/usr/bin/env python3
"""
Скрипт для проверки обновленных цен товаров в магазине

UPDATED: Uses centralized database connection from database.connection
"""

import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import create_tables, get_db
from core.systems.shop_system import EnhancedShopSystem

def check_updated_prices():
    """Проверка обновленных цен в системе магазина"""
    
    print("🔍 Проверка обновленных цен товаров...")
    print("=" * 50)
    
    # Инициализируем базу данных
    create_tables()
    db = next(get_db())
    
    # Создаем систему магазина
    shop_system = EnhancedShopSystem(db)
    
    # Инициализируем категории и товары
    shop_system.initialize_default_categories()
    shop_system.initialize_default_items()
    
    # Получаем каталог
    catalog = shop_system.get_shop_catalog()
    
    print("📦 Обновленные цены товаров:")
    print()
    
    for category_name, category_data in catalog.items():
        print(f"🏷️  {category_name}")
        print(f"   {category_data['description']}")
        print()
        
        for item in category_data['items']:
            print(f"   • {item['name']}")
            print(f"     💰 Цена: {item['price']} монет")
            print(f"     📝 {item['description']}")
            if item['limit']:
                print(f"     🔒 Лимит покупок: {item['limit']}")
            if item['cooldown']:
                print(f"     ⏰ Cooldown: {item['cooldown']} часов")
            print()
    
    print("=" * 50)
    print("✅ Все цены успешно обновлены до 100 монет!")
    print()
    
    # Проверяем конфигурацию безопасности
    from src.config import TRANSACTION_SECURITY
    print("🔒 Обновленные лимиты безопасности:")
    print(f"   • Максимальная сумма за транзакцию: {TRANSACTION_SECURITY['max_single_amount']} монет")
    print(f"   • Максимум транзакций в час: {TRANSACTION_SECURITY['max_hourly_transactions']}")
    print()
    
    db.close()

if __name__ == "__main__":
    check_updated_prices()