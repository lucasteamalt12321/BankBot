# reset_db.py
from database import create_tables, engine
from database import User, UserAlias, Transaction, ShopCategory, ShopItem


def reset_database():
    print("🔄 Пересоздание базы данных...")

    # Удаляем все таблицы
    from sqlalchemy import inspect
    inspector = inspect(engine)

    # Удаляем в правильном порядке (с учетом foreign keys)
    tables = [
        'user_notifications', 'user_achievements', 'achievements',
        'gifts', 'clan_members', 'clans', 'friendships',
        'dnd_quests', 'dnd_dice_rolls', 'dnd_characters', 'dnd_sessions',
        'game_players', 'game_sessions', 'user_purchases', 'shop_items',
        'shop_categories', 'transactions', 'user_aliases', 'users'
    ]

    for table in tables:
        try:
            from sqlalchemy import text
            engine.execute(text(f"DROP TABLE IF EXISTS {table}"))
            print(f"  Удалена таблица: {table}")
        except:
            pass

    # Создаем таблицы заново
    create_tables()
    print("✅ База данных пересоздана")

    # Добавляем тестового пользователя
    from sqlalchemy.orm import Session
    session = Session(bind=engine)

    try:
        # Тестовый пользователь
        user = User(
            telegram_id=7956794368,
            username="CrazyTimeI",
            first_name="Crazy",
            last_name="Time",
            balance=1000
        )
        session.add(user)
        session.commit()
        print(f"✅ Добавлен тестовый пользователь: {user.username}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    reset_database()