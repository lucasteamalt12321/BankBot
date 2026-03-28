#!/usr/bin/env python3
"""
Verification script to check that parsing configuration was correctly migrated
from coefficients.json to the database.

This script:
1. Loads the original coefficients.json file
2. Queries the database for all parsing rules
3. Verifies that all games are present with correct coefficients
4. Checks that all rules are enabled
5. Reports any discrepancies

Usage:
    python scripts/verify_migration.py
"""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database.database import SessionLocal
from src.models.parsing_rule import ParsingRule
from src.repository.base import BaseRepository
from core.managers.parsing_config_manager import ParsingConfigManager


# Mapping of game names from coefficients.json to standardized names
GAME_NAME_MAPPING = {
    "GD Cards": "gdcards",
    "Shmalala": "shmalala",
    "Shmalala Karma": "shmalala_karma",
    "True Mafia": "truemafia",
    "Bunker RP": "bunkerrp"
}


def verify_migration():
    """
    Verify that the migration was successful.
    
    Returns:
        True if verification passed, False otherwise
    """
    print("=" * 60)
    print("Parsing Configuration Migration Verification")
    print("=" * 60)
    print()
    
    # Load original coefficients
    coefficients_path = project_root / "config" / "coefficients.json"
    print(f"📂 Loading original coefficients from: {coefficients_path}")
    
    try:
        with open(coefficients_path, 'r', encoding='utf-8') as f:
            original_coefficients = json.load(f)
        print(f"✅ Loaded {len(original_coefficients)} original game configurations")
        print()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        return False
    
    # Connect to database
    print("🔌 Connecting to database...")
    session = SessionLocal()
    
    try:
        repository = BaseRepository(ParsingRule, session)
        manager = ParsingConfigManager(repository)
        print("✅ Database connection established")
        print()
        
        # Get all rules from database
        print("📋 Retrieving parsing rules from database...")
        all_rules = manager.get_all_rules()
        print(f"✅ Found {len(all_rules)} rules in database")
        print()
        
        # Verification checks
        print("🔍 Running verification checks...")
        print("-" * 60)
        
        all_passed = True
        missing_games = []
        incorrect_coefficients = []
        disabled_rules = []
        
        # Check each game from original coefficients
        for original_name, expected_coefficient in original_coefficients.items():
            game_name = GAME_NAME_MAPPING.get(original_name, original_name.lower().replace(" ", "_"))
            
            print(f"\n✓ Checking: {original_name} → {game_name}")
            
            # Check if rule exists
            if game_name not in all_rules:
                print(f"  ❌ MISSING: Rule not found in database")
                missing_games.append(original_name)
                all_passed = False
                continue
            
            rule = all_rules[game_name]
            
            # Check coefficient
            if rule.coefficient != expected_coefficient:
                print(f"  ❌ COEFFICIENT MISMATCH:")
                print(f"     Expected: {expected_coefficient}")
                print(f"     Found: {rule.coefficient}")
                incorrect_coefficients.append({
                    'game': original_name,
                    'expected': expected_coefficient,
                    'actual': rule.coefficient
                })
                all_passed = False
            else:
                print(f"  ✅ Coefficient correct: {rule.coefficient}")
            
            # Check if enabled
            if not rule.enabled:
                print(f"  ⚠️  WARNING: Rule is disabled")
                disabled_rules.append(original_name)
                all_passed = False
            else:
                print(f"  ✅ Rule is enabled")
            
            # Display additional info
            print(f"  ℹ️  Parser class: {rule.parser_class}")
            print(f"  ℹ️  Database ID: {rule.id}")
        
        print()
        print("-" * 60)
        print("📊 Verification Summary:")
        print(f"   • Total games in coefficients.json: {len(original_coefficients)}")
        print(f"   • Total rules in database: {len(all_rules)}")
        print(f"   • Missing games: {len(missing_games)}")
        print(f"   • Incorrect coefficients: {len(incorrect_coefficients)}")
        print(f"   • Disabled rules: {len(disabled_rules)}")
        print()
        
        # Report issues
        if missing_games:
            print("❌ Missing games:")
            for game in missing_games:
                print(f"   • {game}")
            print()
        
        if incorrect_coefficients:
            print("❌ Incorrect coefficients:")
            for item in incorrect_coefficients:
                print(f"   • {item['game']}: expected {item['expected']}, got {item['actual']}")
            print()
        
        if disabled_rules:
            print("⚠️  Disabled rules:")
            for game in disabled_rules:
                print(f"   • {game}")
            print()
        
        # Display all database rules
        print("📋 All parsing rules in database:")
        print("-" * 60)
        for game_name, rule in sorted(all_rules.items()):
            status = "✅ Enabled" if rule.enabled else "❌ Disabled"
            print(f"   {game_name:20} | Coef: {rule.coefficient:6.1f} | {status} | Parser: {rule.parser_class}")
        
        print()
        print("=" * 60)
        
        if all_passed:
            print("✅ VERIFICATION PASSED: All data migrated correctly!")
        else:
            print("❌ VERIFICATION FAILED: Issues found (see above)")
        
        print("=" * 60)
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ Fatal error during verification: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()
        print("\n🔌 Database connection closed")


if __name__ == "__main__":
    success = verify_migration()
    sys.exit(0 if success else 1)
