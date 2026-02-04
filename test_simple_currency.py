#!/usr/bin/env python3
"""
Simple test for currency conversion and logging functionality
"""

import sys
import os
import tempfile
import asyncio
from decimal import Decimal
from datetime import datetime

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, ParsingRule, ParsedTransaction
from core.message_parser import MessageParser


class MockMessage:
    """Mock message object for testing"""
    def __init__(self, text: str, user_id: int = None):
        self.text = text
        self.from_user = MockUser(user_id) if user_id else None
        self.chat = MockChat(12345)


class MockUser:
    """Mock user object for testing"""
    def __init__(self, user_id: int):
        self.id = user_id


class MockChat:
    """Mock chat object for testing"""
    def __init__(self, chat_id: int):
        self.id = chat_id


async def test_simple_currency_conversion():
    """Simple test for currency conversion and logging"""
    
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        # Create database engine and session
        engine = create_engine(f"sqlite:///{temp_db.name}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Create test user
        user = User(
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            balance=1000,
            is_admin=False
        )
        session.add(user)
        
        # Create test parsing rule
        rule = ParsingRule(
            bot_name='Shmalala',
            pattern=r'Монеты:\s*\+(\d+)',
            multiplier=Decimal('1.5'),
            currency_type='coins',
            is_active=True
        )
        session.add(rule)
        session.commit()
        
        # Initialize message parser
        parser = MessageParser(session)
        
        # Test message
        message_text = "🎣 Рыбалка 🎣\nМонеты: +100 (1000)💰"
        mock_message = MockMessage(message_text, user_id=12345)
        
        # Parse message
        result = await parser.parse_message(mock_message)
        
        # Check results
        if result:
            print(f"✓ Parsing successful")
            print(f"  Original amount: {result.original_amount}")
            print(f"  Converted amount: {result.converted_amount}")
            print(f"  Source bot: {result.source_bot}")
            print(f"  Currency type: {result.currency_type}")
            
            # Check user balance update
            session.refresh(user)
            print(f"  User balance updated: {user.balance}")
            
            # Check transaction logging
            transaction = session.query(ParsedTransaction).filter(
                ParsedTransaction.user_id == 12345
            ).first()
            
            if transaction:
                print(f"✓ Transaction logged successfully")
                print(f"  Transaction ID: {transaction.id}")
                print(f"  Logged amount: {transaction.converted_amount}")
            else:
                print("✗ Transaction not logged")
        else:
            print("✗ Parsing failed")
        
        session.close()
        
    finally:
        try:
            os.unlink(temp_db.name)
        except:
            pass


if __name__ == '__main__':
    asyncio.run(test_simple_currency_conversion())