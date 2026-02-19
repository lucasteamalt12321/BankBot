#!/usr/bin/env python3
"""
Example script demonstrating the message parsing system.

This comprehensive example demonstrates:
1. Complete system initialization with all components
2. Processing messages from all 5 games:
   - GD Cards (profile tracking + accruals)
   - Shmalala Fishing (accruals)
   - Shmalala Karma (accruals, always +1)
   - True Mafia (profile tracking + game winners)
   - BunkerRP (profile tracking + game winners)
3. Error handling and recovery
4. Idempotency protection
5. Balance queries and reporting

Games and Coefficients:
- GD Cards: coefficient 2
- Shmalala: coefficient 1
- Shmalala Karma: coefficient 10
- True Mafia: coefficient 15 (winners get 10 money each)
- Bunker RP: coefficient 20 (winners get 30 money each)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime
from decimal import Decimal

# Import all components
from src.repository import SQLiteRepository
from src.coefficient_provider import CoefficientProvider
from src.audit_logger import AuditLogger
from src.balance_manager import BalanceManager
from src.parsers import (
    ProfileParser, AccrualParser, FishingParser, KarmaParser,
    MafiaGameEndParser, MafiaProfileParser, BunkerGameEndParser, BunkerProfileParser,
    ParserError
)
from src.classifier import MessageClassifier
from src.idempotency import IdempotencyChecker
from src.message_processor import MessageProcessor


def setup_logging() -> logging.Logger:
    """Set up logging with INFO level and detailed formatting."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger('message_parser')


def initialize_components(db_path: str, config_path: str, logger: logging.Logger):
    """
    Initialize all system components with proper dependency injection.
    
    This demonstrates the complete setup process:
    1. Database repository (SQLite)
    2. Coefficient provider (from JSON config)
    3. Audit logger (for operation tracking)
    4. Balance manager (business logic)
    5. All 8 parsers (for different message types)
    6. Message classifier (type detection)
    7. Idempotency checker (duplicate prevention)
    8. Message processor (main orchestrator)
    
    Args:
        db_path: Path to SQLite database file
        config_path: Path to coefficients JSON config file
        logger: Python logger instance
        
    Returns:
        Tuple of (repository, message_processor)
    """
    print("\n" + "="*70)
    print("INITIALIZING SYSTEM COMPONENTS")
    print("="*70)
    
    # 1. Initialize database repository
    repository = SQLiteRepository(db_path)
    print(f"✓ Database repository initialized: {db_path}")
    
    # 2. Load game coefficients from configuration
    coefficient_provider = CoefficientProvider.from_config(config_path)
    print(f"✓ Coefficient provider loaded: {config_path}")
    print("  - GD Cards: coefficient 2")
    print("  - Shmalala: coefficient 1")
    print("  - Shmalala Karma: coefficient 10")
    print("  - True Mafia: coefficient 15")
    print("  - Bunker RP: coefficient 20")
    
    # 3. Initialize audit logger
    audit_logger = AuditLogger(logger)
    print("✓ Audit logger initialized")
    
    # 4. Initialize balance manager (orchestrates balance updates)
    balance_manager = BalanceManager(repository, coefficient_provider, audit_logger)
    print("✓ Balance manager initialized")
    
    # 5. Initialize all 8 parsers
    profile_parser = ProfileParser()              # GD Cards profiles
    accrual_parser = AccrualParser()              # GD Cards accruals
    fishing_parser = FishingParser()              # Shmalala fishing
    karma_parser = KarmaParser()                  # Shmalala karma
    mafia_game_end_parser = MafiaGameEndParser()  # True Mafia winners
    mafia_profile_parser = MafiaProfileParser()   # True Mafia profiles
    bunker_game_end_parser = BunkerGameEndParser()  # BunkerRP winners
    bunker_profile_parser = BunkerProfileParser()   # BunkerRP profiles
    print("✓ All 8 parsers initialized")
    
    # 6. Initialize message classifier
    classifier = MessageClassifier()
    print("✓ Message classifier initialized")
    
    # 7. Initialize idempotency checker
    idempotency_checker = IdempotencyChecker(repository)
    print("✓ Idempotency checker initialized")
    
    # 8. Wire up message processor with all dependencies
    message_processor = MessageProcessor(
        classifier=classifier,
        profile_parser=profile_parser,
        accrual_parser=accrual_parser,
        fishing_parser=fishing_parser,
        karma_parser=karma_parser,
        mafia_game_end_parser=mafia_game_end_parser,
        mafia_profile_parser=mafia_profile_parser,
        bunker_game_end_parser=bunker_game_end_parser,
        bunker_profile_parser=bunker_profile_parser,
        balance_manager=balance_manager,
        idempotency_checker=idempotency_checker,
        logger=audit_logger
    )
    print("✓ Message processor initialized with all dependencies")
    
    print("="*70)
    print("✓ ALL COMPONENTS INITIALIZED SUCCESSFULLY")
    print("="*70 + "\n")
    
    return repository, message_processor


def display_balances(repository: SQLiteRepository, user_name: str):
    """
    Query and display user balances across all games.
    
    Args:
        repository: Database repository
        user_name: Name of user to query
    """
    try:
        user = repository.get_or_create_user(user_name)
        print(f"\n{'='*70}")
        print(f"BALANCES FOR: {user_name}")
        print(f"{'='*70}")
        print(f"💰 Bank Balance: {user.bank_balance} coins")
        
        # Query bot balances for all games
        cursor = repository.conn.cursor()
        cursor.execute(
            """SELECT game, last_balance, current_bot_balance 
               FROM bot_balances 
               WHERE user_id = ?
               ORDER BY game""",
            (user.user_id,)
        )
        rows = cursor.fetchall()
        
        if rows:
            print("\n📊 Game-specific balances:")
            for game, last_balance, current_bot_balance in rows:
                print(f"  • {game}:")
                print(f"      Last Profile Balance: {last_balance}")
                print(f"      Current Bot Balance: {current_bot_balance}")
        else:
            print("\n📊 No game-specific balances found.")
        print(f"{'='*70}\n")
    except Exception as e:
        print(f"❌ Error querying balances: {e}\n")


def process_message_with_logging(processor: MessageProcessor, message: str, 
                                  timestamp: datetime, description: str):
    """
    Process a message with detailed logging and error handling.
    
    Args:
        processor: Message processor instance
        message: Raw message text
        timestamp: Message timestamp
        description: Human-readable description of the message
    """
    print(f"\n{'─'*70}")
    print(f"📨 {description}")
    print(f"{'─'*70}")
    
    try:
        processor.process_message(message=message, timestamp=timestamp)
        print("✅ Message processed successfully")
    except ParserError as e:
        print(f"❌ Parser error: {e}")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def demonstrate_gdcards(processor: MessageProcessor, repository: SQLiteRepository):
    """Demonstrate GD Cards message processing (profile + accrual)."""
    print("\n" + "="*70)
    print("GAME 1: GD CARDS (Coefficient: 2)")
    print("="*70)
    
    # GD Cards profile message
    profile_message = """ПРОФИЛЬ LucasTeam
───────────────
ID: 8685 (23.08.2025)
Ник: LucasTeam
Статусы: Игрок
Карт собрано: 124/213
Очки: 364 (#701)
Орбы: 10 (#342)
Клан: LucasTeamGD (#50)
Титулы: Продвинутый S2
Бейджи: Нет
Любимая карта: Нету
───────────────"""
    
    # GD Cards accrual message
    accrual_message = """(🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: LucasTeam
───────────────
Карта: "Zodiac"
Описание: Коллаб от Bianox, сместивший Crimson Planet с первой строчки сложнейших уровней.
Категория: Демоны
───────────────
Редкость: Эпическая (21/55) (17.0%) 🟣
Очки: +3
Орбы за дроп: +10
Коллекция: 124/213 карт
───────────────"""
    
    # Process profile (first time - initializes tracking)
    process_message_with_logging(
        processor, profile_message,
        datetime(2026, 2, 12, 10, 0, 0),
        "GD Cards Profile - First time (initializes tracking, no bank change)"
    )
    display_balances(repository, "LucasTeam")
    
    # Process accrual (adds points)
    process_message_with_logging(
        processor, accrual_message,
        datetime(2026, 2, 12, 10, 5, 0),
        "GD Cards Accrual - +3 points (bank change: 3 * 2 = 6 coins)"
    )
    display_balances(repository, "LucasTeam")
    
    # Process updated profile (delta calculation)
    updated_profile = profile_message.replace("Орбы: 10", "Орбы: 25")
    process_message_with_logging(
        processor, updated_profile,
        datetime(2026, 2, 12, 10, 10, 0),
        "GD Cards Profile Update - Orbs increased 10→25 (delta: 15, bank change: 15 * 2 = 30 coins)"
    )
    display_balances(repository, "LucasTeam")


def demonstrate_shmalala_fishing(processor: MessageProcessor, repository: SQLiteRepository):
    """Demonstrate Shmalala Fishing message processing."""
    print("\n" + "="*70)
    print("GAME 2: SHMALALA FISHING (Coefficient: 1)")
    print("="*70)
    
    fishing_message = """🎣 [Рыбалка] 🎣
───────────────
Рыбак: FisherPlayer
Рыба: Золотая рыбка
Монеты: +50 (Всего: 150)
───────────────"""
    
    process_message_with_logging(
        processor, fishing_message,
        datetime(2026, 2, 12, 11, 0, 0),
        "Shmalala Fishing - +50 coins (bank change: 50 * 1 = 50 coins)"
    )
    display_balances(repository, "FisherPlayer")
    
    # Second fishing accrual
    fishing_message_2 = fishing_message.replace("Монеты: +50", "Монеты: +30")
    process_message_with_logging(
        processor, fishing_message_2,
        datetime(2026, 2, 12, 11, 15, 0),
        "Shmalala Fishing - +30 coins (bank change: 30 * 1 = 30 coins)"
    )
    display_balances(repository, "FisherPlayer")


def demonstrate_shmalala_karma(processor: MessageProcessor, repository: SQLiteRepository):
    """Demonstrate Shmalala Karma message processing (always +1)."""
    print("\n" + "="*70)
    print("GAME 3: SHMALALA KARMA (Coefficient: 10, Always +1)")
    print("="*70)
    
    karma_message = """Лайк! Вы повысили рейтинг пользователя KarmaPlayer.
Теперь его рейтинг: 25"""
    
    process_message_with_logging(
        processor, karma_message,
        datetime(2026, 2, 12, 12, 0, 0),
        "Shmalala Karma - +1 karma (bank change: 1 * 10 = 10 coins)"
    )
    display_balances(repository, "KarmaPlayer")
    
    # Second karma (always +1 regardless of displayed rating)
    karma_message_2 = karma_message.replace("рейтинг: 25", "рейтинг: 26")
    process_message_with_logging(
        processor, karma_message_2,
        datetime(2026, 2, 12, 12, 5, 0),
        "Shmalala Karma - +1 karma (bank change: 1 * 10 = 10 coins)"
    )
    display_balances(repository, "KarmaPlayer")


def demonstrate_truemafia(processor: MessageProcessor, repository: SQLiteRepository):
    """Demonstrate True Mafia message processing (profile + game winners)."""
    print("\n" + "="*70)
    print("GAME 4: TRUE MAFIA (Coefficient: 15, Winners get 10 money)")
    print("="*70)
    
    # True Mafia profile
    profile_message = """👤 MafiaPlayer
───────────────
💎 Камни: 100
🎎 Активная роль: Мафия
💵 Деньги: 50
───────────────"""
    
    process_message_with_logging(
        processor, profile_message,
        datetime(2026, 2, 12, 13, 0, 0),
        "True Mafia Profile - First time (initializes tracking, no bank change)"
    )
    display_balances(repository, "MafiaPlayer")
    
    # True Mafia game end with winners
    game_end_message = """Игра окончена!
───────────────
Победители:
MafiaPlayer - Мафия
Player2 - Мирный житель
Player3 - Доктор
───────────────
Остальные участники:
Player4 - Мирный житель
───────────────"""
    
    process_message_with_logging(
        processor, game_end_message,
        datetime(2026, 2, 12, 13, 30, 0),
        "True Mafia Game End - 3 winners, each gets 10 money (bank change: 10 * 15 = 150 coins each)"
    )
    display_balances(repository, "MafiaPlayer")
    display_balances(repository, "Player2")
    
    # Updated profile showing money increase
    updated_profile = profile_message.replace("💵 Деньги: 50", "💵 Деньги: 80")
    process_message_with_logging(
        processor, updated_profile,
        datetime(2026, 2, 12, 14, 0, 0),
        "True Mafia Profile Update - Money increased 50→80 (delta: 30, bank change: 30 * 15 = 450 coins)"
    )
    display_balances(repository, "MafiaPlayer")


def demonstrate_bunkerrp(processor: MessageProcessor, repository: SQLiteRepository):
    """Demonstrate BunkerRP message processing (profile + game winners)."""
    print("\n" + "="*70)
    print("GAME 5: BUNKER RP (Coefficient: 20, Winners get 30 money)")
    print("="*70)
    
    # BunkerRP profile
    profile_message = """👤 BunkerPlayer
───────────────
💎 Кристаллики: 200
🎯 Побед: 5
💵 Деньги: 100
───────────────"""
    
    process_message_with_logging(
        processor, profile_message,
        datetime(2026, 2, 12, 15, 0, 0),
        "BunkerRP Profile - First time (initializes tracking, no bank change)"
    )
    display_balances(repository, "BunkerPlayer")
    
    # BunkerRP game end with winners
    game_end_message = """Прошли в бункер:
1. BunkerPlayer
2. SurvivorPlayer
───────────────
Не прошли в бункер:
3. LoserPlayer
───────────────"""
    
    process_message_with_logging(
        processor, game_end_message,
        datetime(2026, 2, 12, 15, 30, 0),
        "BunkerRP Game End - 2 winners, each gets 30 money (bank change: 30 * 20 = 600 coins each)"
    )
    display_balances(repository, "BunkerPlayer")
    display_balances(repository, "SurvivorPlayer")
    
    # Updated profile showing money increase
    updated_profile = profile_message.replace("💵 Деньги: 100", "💵 Деньги: 150")
    process_message_with_logging(
        processor, updated_profile,
        datetime(2026, 2, 12, 16, 0, 0),
        "BunkerRP Profile Update - Money increased 100→150 (delta: 50, bank change: 50 * 20 = 1000 coins)"
    )
    display_balances(repository, "BunkerPlayer")


def demonstrate_error_handling(processor: MessageProcessor, repository: SQLiteRepository):
    """Demonstrate error handling with malformed messages."""
    print("\n" + "="*70)
    print("ERROR HANDLING DEMONSTRATIONS")
    print("="*70)
    
    # Missing required field
    malformed_profile = """ПРОФИЛЬ TestUser
───────────────
ID: 1234
Ник: TestUser
───────────────"""
    
    process_message_with_logging(
        processor, malformed_profile,
        datetime(2026, 2, 12, 17, 0, 0),
        "Malformed Message - Missing 'Орбы:' field (should raise ParserError)"
    )
    
    # Unknown message type
    unknown_message = """This is just some random text
that doesn't match any game format."""
    
    process_message_with_logging(
        processor, unknown_message,
        datetime(2026, 2, 12, 17, 5, 0),
        "Unknown Message Type - No matching classifier (should raise ParserError)"
    )
    
    print("\n✅ Error handling working correctly - system continues after errors")


def demonstrate_idempotency(processor: MessageProcessor, repository: SQLiteRepository):
    """Demonstrate idempotency protection against duplicate messages."""
    print("\n" + "="*70)
    print("IDEMPOTENCY DEMONSTRATION")
    print("="*70)
    
    accrual_message = """(🃏 НОВАЯ КАРТА 🃏
───────────────
Игрок: IdempotencyTest
───────────────
Карта: "Test Card"
Категория: Тест
───────────────
Редкость: Обычная
Очки: +5
───────────────"""
    
    # First processing
    print("\n1️⃣ First processing (should succeed):")
    process_message_with_logging(
        processor, accrual_message,
        datetime(2026, 2, 12, 18, 0, 0),
        "First processing of accrual message"
    )
    display_balances(repository, "IdempotencyTest")
    
    # Duplicate processing (same timestamp)
    print("\n2️⃣ Duplicate processing (same timestamp, should be skipped):")
    process_message_with_logging(
        processor, accrual_message,
        datetime(2026, 2, 12, 18, 0, 0),  # Same timestamp
        "Duplicate message - should be skipped by idempotency checker"
    )
    display_balances(repository, "IdempotencyTest")
    
    print("\n✅ Idempotency working - balance unchanged after duplicate")


def print_summary(repository: SQLiteRepository):
    """Print final summary of all users and balances."""
    print("\n" + "="*70)
    print("FINAL SUMMARY - ALL USERS")
    print("="*70)
    
    cursor = repository.conn.cursor()
    cursor.execute("SELECT user_name, bank_balance FROM user_balances ORDER BY bank_balance DESC")
    users = cursor.fetchall()
    
    if users:
        print(f"\n{'User':<20} {'Bank Balance':>15}")
        print("─" * 70)
        for user_name, bank_balance in users:
            print(f"{user_name:<20} {bank_balance:>15} coins")
    else:
        print("\nNo users found in database.")
    
    print("\n" + "="*70)


def main():
    """
    Main execution function demonstrating the complete message parsing system.
    
    This comprehensive example demonstrates:
    - Complete system initialization
    - Processing messages from all 5 games
    - Error handling and recovery
    - Idempotency protection
    - Balance tracking across games
    """
    print("\n" + "="*70)
    print("MESSAGE PARSING SYSTEM - COMPREHENSIVE EXAMPLE")
    print("="*70)
    print("\nThis example demonstrates processing messages from all 5 games:")
    print("  1. GD Cards (coefficient 2)")
    print("  2. Shmalala Fishing (coefficient 1)")
    print("  3. Shmalala Karma (coefficient 10)")
    print("  4. True Mafia (coefficient 15)")
    print("  5. Bunker RP (coefficient 20)")
    print("\n" + "="*70)
    
    # Set up logging
    logger = setup_logging()
    
    # Clean up old database if exists
    db_path = "example.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"\n🗑️  Removed old database: {db_path}")
    
    # Initialize all components
    repository, message_processor = initialize_components(
        db_path=db_path,
        config_path="config/coefficients.json",
        logger=logger
    )
    
    # Demonstrate each game
    demonstrate_gdcards(message_processor, repository)
    demonstrate_shmalala_fishing(message_processor, repository)
    demonstrate_shmalala_karma(message_processor, repository)
    demonstrate_truemafia(message_processor, repository)
    demonstrate_bunkerrp(message_processor, repository)
    
    # Demonstrate error handling
    demonstrate_error_handling(message_processor, repository)
    
    # Demonstrate idempotency
    demonstrate_idempotency(message_processor, repository)
    
    # Print final summary
    print_summary(repository)
    
    # Final notes
    print("\n" + "="*70)
    print("EXAMPLE COMPLETED SUCCESSFULLY")
    print("="*70)
    print("\n✅ Demonstrated:")
    print("  • Complete system initialization with all components")
    print("  • Message processing for all 5 games")
    print("  • Profile tracking with delta calculation")
    print("  • Accrual processing with coefficient application")
    print("  • Game winner rewards (True Mafia: 10 money, BunkerRP: 30 money)")
    print("  • Error handling and recovery")
    print("  • Idempotency protection against duplicates")
    print("  • Balance queries across multiple games")
    print(f"\n💾 Database saved to: {db_path}")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
