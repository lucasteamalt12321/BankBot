"""
Beta Economy System
Handles market, trading, loans, and investments
"""

import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BetaEconomySystem:
    """Manages beta economy features"""
    
    def __init__(self, db_path: str = "data/bot.db"):
        self.db_path = db_path
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    # ============================================
    # MARKET FUNCTIONS
    # ============================================
    
    def get_market_listings(self, status: str = 'active', limit: int = 10) -> List[Dict]:
        """Get market listings"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ml.*, u.username, u.first_name
            FROM marketplace_listings ml
            JOIN users u ON ml.seller_id = u.id
            WHERE ml.status = ?
            ORDER BY ml.created_at DESC
            LIMIT ?
        """, (status, limit))
        
        columns = [desc[0] for desc in cursor.description]
        listings = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return listings
    
    def create_listing(self, seller_id: int, item_name: str, price: Decimal, 
                      item_type: str = 'custom', item_id: Optional[int] = None,
                      description: Optional[str] = None) -> Optional[int]:
        """Create a new market listing"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            expires_at = datetime.now() + timedelta(days=7)
            
            cursor.execute("""
                INSERT INTO marketplace_listings 
                (seller_id, item_type, item_id, item_name, price, description, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (seller_id, item_type, item_id, item_name, float(price), description, expires_at))
            
            conn.commit()
            listing_id = cursor.lastrowid
            logger.info(f"Created listing {listing_id} by user {seller_id}")
            return listing_id
            
        except Exception as e:
            logger.error(f"Error creating listing: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
