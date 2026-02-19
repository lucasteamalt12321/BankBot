#!/usr/bin/env python3
"""Проверка истории транзакций пользователя"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.database import get_db, Transaction, User
from sqlalchemy import desc
from src.config import settings

# ID пользователя
user_telegram_id = settings.ADMIN_TELEGRAM_ID

db = next(get_db())
try:
    # Находим пользователя
    user = db.query(User).filter(User.telegram_id == user_telegram_id).first()
    
    if not user:
        print(f"❌ Пользователь с ID {user_telegram_id} не найден")
        sys.exit(1)
    
    print(f"👤 Пользователь: {user.username or user.first_name}")
    print(f"💳 Баланс: {user.balance} монет")
    print(f"🆔 User ID в БД: {user.id}")
    print()
    
    # Получаем все транзакции
    transactions = db.query(Transaction).filter(
        Transaction.user_id == user.id
    ).order_by(desc(Transaction.created_at)).all()
    
    print(f"📊 Всего транзакций: {len(transactions)}")
    print()
    
    # Группируем по типам
    types_count = {}
    for t in transactions:
        types_count[t.transaction_type] = types_count.get(t.transaction_type, 0) + 1
    
    print("📈 По типам:")
    for ttype, count in types_count.items():
        print(f"  • {ttype}: {count}")
    print()
    
    # Показываем последние 10 транзакций
    print("📝 Последние 10 транзакций:")
    for i, t in enumerate(transactions[:10], 1):
        amount_str = f"+{t.amount}" if t.amount > 0 else str(t.amount)
        print(f"{i}. [{t.transaction_type}] {amount_str} монет")
        print(f"   {t.description}")
        print(f"   {t.created_at.strftime('%d.%m.%Y %H:%M:%S')}")
        if t.source_game:
            print(f"   Игра: {t.source_game}")
        print()
    
    # Проверяем profile_sync транзакции
    profile_syncs = [t for t in transactions if t.transaction_type == 'profile_sync']
    print(f"🔄 Синхронизаций профиля: {len(profile_syncs)}")
    if profile_syncs:
        print("   Последняя синхронизация:")
        last_sync = profile_syncs[0]
        print(f"   {last_sync.description}")
        print(f"   {last_sync.created_at.strftime('%d.%m.%Y %H:%M:%S')}")
    
finally:
    db.close()
