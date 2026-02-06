#!/usr/bin/env python3
"""
Unit tests for Advanced Telegram Bot Features database schema and data models
Tests the new tables, columns, and data model functionality
"""

import pytest
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database import Base, User, ParsingRule, ParsedTransaction, PurchaseRecord, ShopItem
from core.models.advanced_models import (
    EnhancedUser, ShopItem as AdvancedShopItem, ParsingRule as AdvancedParsingRule,
    ParsedTransaction as AdvancedParsedTransaction, PurchaseRecord as AdvancedPurchaseRecord,
    PurchaseResult, BroadcastResult, ParsingResult, UserStats, ParsingStats
)


class TestAdvancedDatabaseSchema:
    """Test suite for advanced database schema"""
    
    @classmethod
    def setup_class(cls):
        """Set up test database"""
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
    
    def setup_method(self):
        """Set up each test method"""
        self.db = self.SessionLocal()
    
    def teardown_method(self):
        """Clean up after each test method"""
        self.db.close()
    
    def test_user_table_new_columns(self):
        """Test that users table has new columns for advanced features"""
        # Create a user with new fields
        user = User(
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            balance=1000,
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() + timedelta(hours=24),
            total_purchases=5
        )
        
        self.db.add(user)
        self.db.commit()
        
        # Retrieve and verify
        retrieved_user = self.db.query(User).filter(User.telegram_id == 12345).first()
        assert retrieved_user is not None
        assert retrieved_user.sticker_unlimited is True
        assert retrieved_user.sticker_unlimited_until is not None
        assert retrieved_user.total_purchases == 5
    
    def test_parsing_rule_table(self):
        """Test parsing_rules table functionality"""
        # Create a parsing rule
        rule = ParsingRule(
            bot_name="TestBot",
            pattern=r"Coins: \+(\d+)",
            multiplier=Decimal('1.5'),
            currency_type="coins",
            is_active=True
        )
        
        self.db.add(rule)
        self.db.commit()
        
        # Retrieve and verify
        retrieved_rule = self.db.query(ParsingRule).filter(ParsingRule.bot_name == "TestBot").first()
        assert retrieved_rule is not None
        assert retrieved_rule.pattern == r"Coins: \+(\d+)"
        assert retrieved_rule.multiplier == Decimal('1.5')
        assert retrieved_rule.currency_type == "coins"
        assert retrieved_rule.is_active is True
    
    def test_parsed_transaction_table(self):
        """Test parsed_transactions table functionality"""
        # Create a user first
        user = User(telegram_id=12346, username="testuser2", balance=1000)
        self.db.add(user)
        self.db.commit()
        
        # Create a parsed transaction
        transaction = ParsedTransaction(
            user_id=user.id,
            source_bot="TestBot",
            original_amount=Decimal('100.00'),
            converted_amount=Decimal('150.00'),
            currency_type="coins",
            parsed_at=datetime.utcnow(),
            message_text="TestBot: Coins: +100"
        )
        
        self.db.add(transaction)
        self.db.commit()
        
        # Retrieve and verify
        retrieved_transaction = self.db.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user.id
        ).first()
        assert retrieved_transaction is not None
        assert retrieved_transaction.source_bot == "TestBot"
        assert retrieved_transaction.original_amount == Decimal('100.00')
        assert retrieved_transaction.converted_amount == Decimal('150.00')
        assert retrieved_transaction.currency_type == "coins"
        assert "Coins: +100" in retrieved_transaction.message_text
    
    def test_purchase_record_table(self):
        """Test purchase_records table functionality"""
        # Create user and shop item first
        user = User(telegram_id=12347, username="testuser3", balance=1000)
        self.db.add(user)
        self.db.commit()
        
        shop_item = ShopItem(
            name="Test Item",
            price=100,
            description="Test item",
            item_type="custom",
            is_active=True
        )
        self.db.add(shop_item)
        self.db.commit()
        
        # Create a purchase record
        purchase = PurchaseRecord(
            user_id=user.id,
            item_id=shop_item.id,
            price_paid=Decimal('100.00'),
            purchased_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        self.db.add(purchase)
        self.db.commit()
        
        # Retrieve and verify
        retrieved_purchase = self.db.query(PurchaseRecord).filter(
            PurchaseRecord.user_id == user.id
        ).first()
        assert retrieved_purchase is not None
        assert retrieved_purchase.item_id == shop_item.id
        assert retrieved_purchase.price_paid == Decimal('100.00')
        assert retrieved_purchase.expires_at is not None


class TestAdvancedDataModels:
    """Test suite for advanced data models"""
    
    def test_enhanced_user_model(self):
        """Test EnhancedUser dataclass"""
        user = EnhancedUser(
            id=1,
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            last_name="User",
            balance=Decimal('1000.00'),
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() + timedelta(hours=24),
            total_purchases=5
        )
        
        assert user.id == 1
        assert user.telegram_id == 12345
        assert user.sticker_unlimited is True
        assert user.total_purchases == 5
        assert isinstance(user.balance, Decimal)
    
    def test_advanced_shop_item_model(self):
        """Test AdvancedShopItem dataclass"""
        item = AdvancedShopItem(
            id=1,
            name="Unlimited Stickers",
            price=Decimal('100.00'),
            item_type="sticker",
            description="24-hour unlimited sticker access"
        )
        
        assert item.id == 1
        assert item.name == "Unlimited Stickers"
        assert item.item_type == "sticker"
        assert isinstance(item.price, Decimal)
    
    def test_parsing_rule_model(self):
        """Test AdvancedParsingRule dataclass"""
        rule = AdvancedParsingRule(
            id=1,
            bot_name="TestBot",
            pattern=r"Coins: \+(\d+)",
            multiplier=Decimal('1.5'),
            currency_type="coins"
        )
        
        assert rule.id == 1
        assert rule.bot_name == "TestBot"
        assert rule.pattern == r"Coins: \+(\d+)"
        assert isinstance(rule.multiplier, Decimal)
    
    def test_parsed_transaction_model(self):
        """Test AdvancedParsedTransaction dataclass"""
        transaction = AdvancedParsedTransaction(
            id=1,
            user_id=123,
            source_bot="TestBot",
            original_amount=Decimal('100.00'),
            converted_amount=Decimal('150.00'),
            currency_type="coins",
            parsed_at=datetime.utcnow(),
            message_text="TestBot: Coins: +100"
        )
        
        assert transaction.id == 1
        assert transaction.user_id == 123
        assert transaction.source_bot == "TestBot"
        assert isinstance(transaction.original_amount, Decimal)
        assert isinstance(transaction.converted_amount, Decimal)
    
    def test_purchase_record_model(self):
        """Test AdvancedPurchaseRecord dataclass"""
        purchase = AdvancedPurchaseRecord(
            id=1,
            user_id=123,
            item_id=456,
            price_paid=Decimal('100.00'),
            purchased_at=datetime.utcnow()
        )
        
        assert purchase.id == 1
        assert purchase.user_id == 123
        assert purchase.item_id == 456
        assert isinstance(purchase.price_paid, Decimal)
    
    def test_result_models(self):
        """Test result dataclasses"""
        # Test PurchaseResult
        purchase_result = PurchaseResult(
            success=True,
            message="Purchase successful",
            purchase_id=123,
            new_balance=Decimal('900.00')
        )
        assert purchase_result.success is True
        assert purchase_result.purchase_id == 123
        
        # Test BroadcastResult
        broadcast_result = BroadcastResult(
            total_users=100,
            successful_sends=95,
            failed_sends=5,
            errors=["User 123 blocked bot"],
            completion_message="Broadcast completed"
        )
        assert broadcast_result.total_users == 100
        assert broadcast_result.successful_sends == 95
        
        # Test ParsingResult
        parsing_result = ParsingResult(
            success=True,
            parsed_amount=Decimal('100.00'),
            converted_amount=Decimal('150.00'),
            source_bot="TestBot"
        )
        assert parsing_result.success is True
        assert isinstance(parsing_result.parsed_amount, Decimal)
    
    def test_stats_models(self):
        """Test statistics dataclasses"""
        # Test UserStats
        user_stats = UserStats(
            user_id=123,
            username="testuser",
            current_balance=Decimal('1000.00'),
            total_purchases=5,
            active_subscriptions=["sticker_unlimited"],
            last_activity=datetime.utcnow(),
            parsing_transactions=[]
        )
        assert user_stats.user_id == 123
        assert user_stats.total_purchases == 5
        
        # Test ParsingStats
        parsing_stats = ParsingStats(
            timeframe="24h",
            total_transactions=100,
            total_amount_converted=Decimal('5000.00'),
            successful_parses=95,
            failed_parses=5,
            transactions_by_bot={"TestBot": 50, "OtherBot": 45},
            amounts_by_bot={"TestBot": Decimal('2500.00'), "OtherBot": Decimal('2250.00')}
        )
        assert parsing_stats.total_transactions == 100
        assert parsing_stats.successful_parses == 95


class TestDatabaseIntegration:
    """Test database integration with advanced features"""
    
    @classmethod
    def setup_class(cls):
        """Set up test database"""
        cls.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
    
    def setup_method(self):
        """Set up each test method"""
        self.db = self.SessionLocal()
    
    def teardown_method(self):
        """Clean up after each test method"""
        self.db.close()
    
    def test_foreign_key_relationships(self):
        """Test foreign key relationships work correctly"""
        # Create user
        user = User(telegram_id=12349, username="testuser5", balance=1000)
        self.db.add(user)
        self.db.commit()
        
        # Create shop item
        shop_item = ShopItem(
            name="Test Item",
            price=100,
            description="Test item",
            item_type="custom"
        )
        self.db.add(shop_item)
        self.db.commit()
        
        # Create parsed transaction
        parsed_tx = ParsedTransaction(
            user_id=user.id,
            source_bot="TestBot",
            original_amount=Decimal('100.00'),
            converted_amount=Decimal('100.00'),
            currency_type="coins",
            message_text="Test message"
        )
        self.db.add(parsed_tx)
        
        # Create purchase record
        purchase = PurchaseRecord(
            user_id=user.id,
            item_id=shop_item.id,
            price_paid=Decimal('100.00')
        )
        self.db.add(purchase)
        self.db.commit()
        
        # Verify relationships
        assert parsed_tx.user == user
        assert purchase.user == user
        assert purchase.item == shop_item
    
    def test_decimal_precision(self):
        """Test that decimal fields maintain precision"""
        # Create parsing rule with precise multiplier
        rule = ParsingRule(
            bot_name="TestBot",
            pattern=r"Test: \+(\d+)",
            multiplier=Decimal('1.2345'),
            currency_type="coins"
        )
        self.db.add(rule)
        self.db.commit()
        
        # Retrieve and verify precision is maintained
        retrieved_rule = self.db.query(ParsingRule).first()
        assert retrieved_rule.multiplier == Decimal('1.2345')
        
        # Test with transaction amounts
        user = User(telegram_id=12348, username="testuser4", balance=1000)
        self.db.add(user)
        self.db.commit()
        
        transaction = ParsedTransaction(
            user_id=user.id,
            source_bot="TestBot",
            original_amount=Decimal('123.45'),
            converted_amount=Decimal('152.46'),
            currency_type="coins",
            message_text="Test"
        )
        self.db.add(transaction)
        self.db.commit()
        
        retrieved_tx = self.db.query(ParsedTransaction).filter(
            ParsedTransaction.user_id == user.id
        ).first()
        assert retrieved_tx.original_amount == Decimal('123.45')
        assert retrieved_tx.converted_amount == Decimal('152.46')


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])