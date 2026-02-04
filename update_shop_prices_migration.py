#!/usr/bin/env python3
"""
Миграция для обновления цен товаров в магазине до 100 монет
"""

import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import create_tables, get_db, ShopItem
from sqlalchemy.orm import Session

def update_shop_prices():
    """Обновление цен товаров в базе данных"""
    
    print("🔄 Обновление цен товаров в базе данных...")
    print("=" * 50)
    
    # Инициализируем базу данных
    create_tables()
    db = next(get_db())
    
    try:
        # Маппинг старых цен на новые
        price_updates = {
            "Безлимитные стикеры (24ч)": 100,
            "Премиум стикерпак": 100,
            "Админка на день": 100,
            "VIP статус (неделя)": 100,
            "Двойной опыт (2ч)": 100,
            "Бонус к балансу (+1000)": 100,
            "Персональная команда": 100,
            "Кастомный заголовок": 100
        }
        
        updated_count = 0
        
        for item_name, new_price in price_updates.items():
            item = db.query(ShopItem).filter(ShopItem.name == item_name).first()
            if item:
                old_price = item.price
                item.price = new_price
                print(f"✅ {item_name}: {old_price} → {new_price} монет")
                updated_count += 1
            else:
                print(f"⚠️  Товар '{item_name}' не найден в базе данных")
        
        # Также обновим описание бонуса к балансу
        bonus_item = db.query(ShopItem).filter(ShopItem.name == "Бонус к балансу (+1000)").first()
        if bonus_item:
            bonus_item.name = "Бонус к балансу (+100)"
            bonus_item.description = "Мгновенное начисление 100 банковских монет"
            # Обновляем meta_data для корректного начисления
            if bonus_item.meta_data:
                bonus_item.meta_data["amount"] = 100
            print("✅ Обновлено описание и сумма бонуса к балансу")
        
        # Сохраняем изменения
        db.commit()
        
        print("=" * 50)
        print(f"✅ Успешно обновлено {updated_count} товаров!")
        print("💰 Все цены теперь составляют 100 монет")
        
        # Проверяем результат
        print("\n📦 Текущие цены товаров:")
        items = db.query(ShopItem).filter(ShopItem.is_active == True).all()
        for item in items:
            print(f"   • {item.name}: {item.price} монет")
            
    except Exception as e:
        print(f"❌ Ошибка при обновлении цен: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_shop_prices()