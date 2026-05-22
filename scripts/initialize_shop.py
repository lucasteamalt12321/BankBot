#!/usr/bin/env python3
"""
Initialize an empty shop category scaffold.

Default/demo shop items are intentionally not created. The production shop is
filled manually through admin tools.
"""

import os
import sys

# Add root directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db, ShopCategory, ShopItem
import structlog

logger = structlog.get_logger()


def initialize_shop():
    """Initialize shop categories without creating default items."""

    try:
        db = next(get_db())

        # Check if shop items already exist
        existing_items = db.query(ShopItem).count()
        if existing_items > 0:
            print(f"Shop already has {existing_items} items. Skipping initialization.")
            return

        print("Initializing empty shop categories...")

        # Create default category
        category = ShopCategory(
            name="Основные услуги",
            description="Основные услуги бота",
            sort_order=1,
            is_active=True
        )
        db.add(category)
        db.commit()
        db.refresh(category)

        print("Shop categories initialized. No default items were created.")

    except Exception as e:
        logger.error(f"Error initializing shop: {e}")
        print(f"Error initializing shop: {e}")
        return False

    return True


if __name__ == "__main__":
    print("Initializing shop...")
    success = initialize_shop()
    if success:
        print("Shop initialization completed successfully!")
    else:
        print("Shop initialization failed!")
        sys.exit(1)
