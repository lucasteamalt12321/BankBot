#!/usr/bin/env python3
"""
Скрипт для обновления достижений в базе данных

UPDATED: Uses centralized database connection from database.connection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, Achievement
from core.systems.achievements import AchievementSystem

def update_achievements():
    """Обновить достижения в базе данных"""
    
    # Подключение к базе данных
    engine = create_engine('sqlite:///data/bot.db')
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("🔄 Обновление системы достижений...")
        
        # Создаем экземпляр системы достижений
        AchievementSystem(session)
        
        # Получаем все достижения из базы
        all_achievements = session.query(Achievement).all()
        
        print(f"✅ Найдено достижений в базе: {len(all_achievements)}")
        
        # Выводим список всех достижений
        categories = {}
        for ach in all_achievements:
            if ach.category not in categories:
                categories[ach.category] = []
            categories[ach.category].append(ach)
        
        tier_emojis = {
            'platinum': '💎',
            'gold': '🥇',
            'silver': '🥈',
            'bronze': '🥉'
        }
        
        print("\n📋 Список всех достижений:")
        print("=" * 50)
        
        for category, achievements in categories.items():
            print(f"\n📂 {category.upper()}:")
            for ach in achievements:
                emoji = tier_emojis.get(ach.tier, '🏅')
                print(f"  {emoji} {ach.name} ({ach.points} очков)")
                print(f"     {ach.description}")
        
        total_points = sum(ach.points for ach in all_achievements)
        print(f"\n💰 Общее количество очков: {total_points}")
        print(f"🎯 Всего достижений: {len(all_achievements)}")
        
        session.commit()
        print("\n✅ Система достижений успешно обновлена!")
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении достижений: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    update_achievements()