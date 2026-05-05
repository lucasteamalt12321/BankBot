#!/usr/bin/env python3
"""
Script to migrate parsing coefficients from coefficients.json to database (Task 7.3)

Usage:
    python scripts/migrate_coefficients.py [--dry-run] [--force]

Options:
    --dry-run    Preview changes without modifying database
    --force      Overwrite existing rules in database
"""

import json
import sys
from pathlib import Path
from decimal import Decimal
import argparse

from database.database import get_db, ParsingRule
from utils.logging.logging_config import logger


# Default coefficients from coefficients.json
DEFAULT_COEFFICIENTS = {
    "gdcards": {
        "pattern": r".*",
        "coefficient": Decimal("2.0"),
        "currency_type": "coins"
    },
    "shmalala": {
        "pattern": r".*",
        "coefficient": Decimal("1.0"),
        "currency_type": "coins"
    },
    "truemafia": {
        "pattern": r".*",
        "coefficient": Decimal("15.0"),
        "currency_type": "coins"
    },
    "bunkerrp": {
        "pattern": r".*",
        "coefficient": Decimal("20.0"),
        "currency_type": "coins"
    }
}


def load_coefficients_from_file(filepath: Path) -> dict:
    """
    Load coefficients from JSON file.
    
    Args:
        filepath: Path to coefficients.json
        
    Returns:
        Dictionary with coefficients
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            coefficients = json.load(f)

        logger.info(f"Loaded coefficients from {filepath}")
        return coefficients

    except FileNotFoundError:
        logger.warning(f"Coefficients file not found: {filepath}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing coefficients file: {e}")
        return {}


def migrate_coefficients(dry_run: bool = False, force: bool = False) -> dict:
    """
    Migrate coefficients from JSON to database.
    
    Args:
        dry_run: If True, don't commit changes
        force: If True, overwrite existing rules
        
    Returns:
        Dictionary with migration statistics
    """
    stats = {
        'total': 0,
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }

    # Get coefficients from file
    coefficients_file = Path("config/coefficients.json")
    coefficients = load_coefficients_from_file(coefficients_file)

    # If file not found, use defaults
    if not coefficients:
        coefficients = DEFAULT_COEFFICIENTS
        logger.info("Using default coefficients")

    # Get database session
    db = next(get_db())

    try:
        for game_name, config in coefficients.items():
            stats['total'] += 1

            # Extract configuration
            pattern = config.get('pattern', '.*')
            coefficient = Decimal(str(config.get('coefficient', 1)))
            currency_type = config.get('currency_type', 'coins')

            # Check if rule already exists
            existing_rule = db.query(ParsingRule).filter(
                ParsingRule.bot_name == game_name,
                ParsingRule.pattern == pattern
            ).first()

            if existing_rule:
                if force:
                    # Update existing rule
                    existing_rule.multiplier = coefficient
                    existing_rule.currency_type = currency_type
                    existing_rule.is_active = True

                    stats['updated'] += 1
                    logger.info(f"Updated rule for {game_name}: {coefficient}")
                else:
                    stats['skipped'] += 1
                    logger.info(f"Skipping existing rule for {game_name}")
            else:
                # Create new rule
                new_rule = ParsingRule(
                    bot_name=game_name,
                    pattern=pattern,
                    multiplier=coefficient,
                    currency_type=currency_type,
                    is_active=True
                )

                db.add(new_rule)
                stats['created'] += 1
                logger.info(f"Created rule for {game_name}: {coefficient}")

        # Commit changes
        if not dry_run:
            db.commit()
            logger.info("Changes committed to database")
        else:
            db.rollback()
            logger.info("Dry run - changes rolled back")

        return stats

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        db.rollback()
        stats['errors'] += 1
        return stats
    finally:
        db.close()


def print_migration_report(stats: dict, dry_run: bool = False):
    """
    Print migration statistics report.
    
    Args:
        stats: Migration statistics dictionary
        dry_run: If True, indicate dry run mode
    """
    print(f"\n{'='*60}")
    print("Migration Report")
    print('='*60)

    if dry_run:
        print("Mode: DRY RUN (no changes committed)")
        print('='*60)

    print(f"\nTotal rules processed: {stats['total']}")
    print(f"Rules created: {stats['created']}")
    print(f"Rules updated: {stats['updated']}")
    print(f"Rules skipped: {stats['skipped']}")
    print(f"Errors: {stats['errors']}")

    if stats['errors'] > 0:
        print("\n⚠️  Some errors occurred during migration")
    else:
        print("\n✅ Migration completed successfully")

    if dry_run:
        print("\n💡 To apply changes, run without --dry-run")
        print("   python scripts/migrate_coefficients.py")

    print('='*60)


def main():
    """Main entry point."""
    # Fix encoding for Windows console
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description='Migrate parsing coefficients from JSON to database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration without changes
  python scripts/migrate_coefficients.py --dry-run
  
  # Apply migration
  python scripts/migrate_coefficients.py
  
  # Force update existing rules
  python scripts/migrate_coefficients.py --force
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying database'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing rules in database'
    )

    args = parser.parse_args()

    print("🔧 Coefficient Migration")
    print('='*60)
    print(f"Mode: {'DRY RUN' if args.dry_run else 'APPLY CHANGES'}")
    print(f"Force: {'Yes' if args.force else 'No'}")
    print('='*60)

    # Run migration
    stats = migrate_coefficients(dry_run=args.dry_run, force=args.force)

    # Print report
    print_migration_report(stats, dry_run=args.dry_run)

    # Exit with appropriate code
    if stats['errors'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
