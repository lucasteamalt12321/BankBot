#!/usr/bin/env python3
"""
Test the full flow including bank system
"""

import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.parsers import UniversalParser
from core.bank_system import BankSystem
from database.database import create_tables, get_db
from utils.user_manager import UserManager

def test_full_flow():
    """Test the complete flow from message to transaction"""
    
    original_sample = '''🖼 🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: TidalWaveT
───────────────
Карта: "Void Wave"
Описание: Один из лучших проектов Cherry Team. Мегаколлаб, выполненный в глоу-стиле длиной в 4 минуты. Верифицирован Dorami.
Категория: Демоны
───────────────
Редкость: Эпическая (1/55) (17.0%) 🟣
Очки: +3
Коллекция: 2/213 карт
───────────────
Эта карта есть у: 994 игроков
Лимит карт сегодня: 1 из 8'''

    print("Testing full flow...")
    print("=" * 50)
    print("Sample message processed...")
    
    # Create database connection
    create_tables()
    db_gen = get_db()
    try:
        db = next(db_gen)
        
        # Test the universal parser first
        universal_parser = UniversalParser()
        parsed_activities = universal_parser.parse_message(original_sample)
        print(f"Universal parser found {len(parsed_activities)} activities")
        for i, activity in enumerate(parsed_activities):
            print(f"  Activity {i+1}: {activity.activity_type} for {activity.user_identifier} - {activity.points} points from {activity.game_source}")
        
        # Initialize bank system
        bank = BankSystem(db)
        
        # Check currency configuration
        print(f"\nGDcards configuration: {bank.currency_config.get('gdcards', 'Not found')}")
        
        # Test currency conversion
        if parsed_activities:
            activity = parsed_activities[0]
            converted = bank.convert_currency(activity.points, activity.game_source, activity.activity_type)
            print(f"\nCurrency conversion: {activity.points} points -> {converted} banking coins")
        
        # Test message processing (this is what happens in the bot)
        print("\nTesting message processing (full flow)...")
        results = bank.process_message(original_sample)
        print(f"Process message returned {len(results)} results")
        
        for i, result in enumerate(results):
            print(f"  Result {i+1}:")
            if result.get('success'):
                print(f"    Success: {result['success']}")
                print(f"    User: {result['user_name']}")
                print(f"    Original points: {result['original_points']}")
                print(f"    Converted amount: {result['converted_amount']}")
                print(f"    New balance: {result['new_balance']}")
                print(f"    Transaction ID: {result['transaction_id']}")
            else:
                print(f"    Success: {result['success']}")
                print(f"    Error: {result.get('error', 'Unknown error')}")
        
        # Check if the transaction was saved
        if results and results[0].get('success'):
            from database.database import Transaction
            latest_transactions = db.query(Transaction).order_by(Transaction.id.desc()).limit(3).all()
            print(f"\nLatest transactions in DB: {len(latest_transactions)}")
            for t in latest_transactions:
                print(f"  Transaction ID: {t.id}, User ID: {t.user_id}, Amount: {t.amount}, Type: {t.transaction_type}, Source: {t.source_game}")
    
    finally:
        db.close()

def test_user_identification():
    """Test user identification process"""
    
    print("\nTesting user identification...")
    print("=" * 50)
    
    # Create database connection
    create_tables()
    db_gen = get_db()
    try:
        db = next(db_gen)
        
        # Initialize user manager
        user_manager = UserManager(db)
        
        # Test identifying a user
        user_identifier = "TidalWaveT"
        user = user_manager.identify_user(user_identifier)
        print(f"Identified user: ID={user.id}, Name={user.first_name}, Username={user.username}, Balance={user.balance}")
        
    finally:
        db.close()

if __name__ == "__main__":
    print("Full Flow Test")
    print("=" * 50)
    
    test_user_identification()
    test_full_flow()
    
    print("\nFull flow test completed!")