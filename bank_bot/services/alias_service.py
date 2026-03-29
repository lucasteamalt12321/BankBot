"""
Service for managing user aliases and nicknames.

This service handles:
- Adding/removing user aliases from different game sources
- Finding users by their aliases
- Managing alias confidence scores
- Fallback to username/first_name when alias not found
"""

from typing import Optional, List, Dict
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from database.database import User, UserAlias
from database.connection import get_connection


class AliasService:
    """Service for managing user aliases and identity resolution."""
    
    def __init__(self, session: Optional[Session] = None):
        """
        Initialize AliasService.
        
        Args:
            session: Optional SQLAlchemy session. If not provided, creates new connection.
        """
        self.session = session
        self._owns_session = session is None
        if self._owns_session:
            self.session = get_connection()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close session if we own it."""
        if self._owns_session and self.session:
            self.session.close()
    
    def add_alias(
        self,
        user_id: int,
        alias_value: str,
        alias_type: str = "nickname",
        game_source: Optional[str] = None,
        confidence_score: float = 1.0
    ) -> UserAlias:
        """
        Add a new alias for a user.
        
        Args:
            user_id: User's database ID
            alias_value: The alias/nickname value
            alias_type: Type of alias (nickname, game_name, etc.)
            game_source: Source game (gdcards, shmalala, bunkerrp, truemafia)
            confidence_score: Confidence score (0.0 to 1.0)
        
        Returns:
            Created UserAlias object
        
        Raises:
            ValueError: If user doesn't exist or alias already exists
        """
        # Verify user exists
        user = self.session.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        
        # Check if alias already exists for this user
        existing = self.session.query(UserAlias).filter_by(
            user_id=user_id,
            alias_value=alias_value,
            game_source=game_source
        ).first()
        
        if existing:
            # Update confidence score if alias exists
            existing.confidence_score = max(existing.confidence_score, confidence_score)
            self.session.commit()
            return existing
        
        # Create new alias
        alias = UserAlias(
            user_id=user_id,
            alias_type=alias_type,
            alias_value=alias_value,
            game_source=game_source,
            confidence_score=confidence_score,
            created_at=datetime.utcnow()
        )
        
        self.session.add(alias)
        self.session.commit()
        
        return alias
    
    def remove_alias(
        self,
        user_id: int,
        alias_value: str,
        game_source: Optional[str] = None
    ) -> bool:
        """
        Remove an alias from a user.
        
        Args:
            user_id: User's database ID
            alias_value: The alias value to remove
            game_source: Optional game source filter
        
        Returns:
            True if alias was removed, False if not found
        """
        query = self.session.query(UserAlias).filter_by(
            user_id=user_id,
            alias_value=alias_value
        )
        
        if game_source:
            query = query.filter_by(game_source=game_source)
        
        alias = query.first()
        
        if alias:
            self.session.delete(alias)
            self.session.commit()
            return True
        
        return False
    
    def get_user_aliases(
        self,
        user_id: int,
        game_source: Optional[str] = None
    ) -> List[UserAlias]:
        """
        Get all aliases for a user.
        
        Args:
            user_id: User's database ID
            game_source: Optional filter by game source
        
        Returns:
            List of UserAlias objects
        """
        query = self.session.query(UserAlias).filter_by(user_id=user_id)
        
        if game_source:
            query = query.filter_by(game_source=game_source)
        
        return query.order_by(UserAlias.confidence_score.desc()).all()
    
    def find_user_by_alias(
        self,
        alias_value: str,
        game_source: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> Optional[User]:
        """
        Find a user by their alias.
        
        Args:
            alias_value: The alias to search for
            game_source: Optional filter by game source
            min_confidence: Minimum confidence score (default 0.5)
        
        Returns:
            User object if found, None otherwise
        """
        query = self.session.query(UserAlias).filter_by(alias_value=alias_value)
        
        if game_source:
            query = query.filter_by(game_source=game_source)
        
        query = query.filter(UserAlias.confidence_score >= min_confidence)
        query = query.order_by(UserAlias.confidence_score.desc())
        
        alias = query.first()
        
        if alias:
            return self.session.query(User).filter_by(id=alias.user_id).first()
        
        return None
    
    def find_user_by_name_or_alias(
        self,
        name: str,
        game_source: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> Optional[User]:
        """
        Find user by alias with fallback to username/first_name.
        
        This is the main method parsers should use for user identification.
        
        Search order:
        1. Exact alias match (with game_source if provided)
        2. Username match (case-insensitive)
        3. First name match (case-insensitive)
        
        Args:
            name: Name or alias to search for
            game_source: Optional game source for alias lookup
            min_confidence: Minimum confidence score for alias match
        
        Returns:
            User object if found, None otherwise
        """
        # Try alias first
        user = self.find_user_by_alias(name, game_source, min_confidence)
        if user:
            return user
        
        # Fallback to username (case-insensitive)
        user = self.session.query(User).filter(
            func.lower(User.username) == func.lower(name)
        ).first()
        if user:
            return user
        
        # Fallback to first_name (case-insensitive)
        user = self.session.query(User).filter(
            func.lower(User.first_name) == func.lower(name)
        ).first()
        if user:
            return user
        
        return None
    
    def get_alias_stats(self, user_id: int) -> Dict[str, int]:
        """
        Get statistics about user's aliases.
        
        Args:
            user_id: User's database ID
        
        Returns:
            Dictionary with alias statistics
        """
        aliases = self.get_user_aliases(user_id)
        
        stats = {
            "total": len(aliases),
            "by_game": {},
            "by_type": {}
        }
        
        for alias in aliases:
            # Count by game source
            game = alias.game_source or "unknown"
            stats["by_game"][game] = stats["by_game"].get(game, 0) + 1
            
            # Count by type
            alias_type = alias.alias_type or "unknown"
            stats["by_type"][alias_type] = stats["by_type"].get(alias_type, 0) + 1
        
        return stats
    
    def sync_alias_from_parser(
        self,
        telegram_id: int,
        game_name: str,
        game_source: str,
        confidence_score: float = 0.9
    ) -> Optional[UserAlias]:
        """
        Sync alias from parser result.
        
        This method is called by parsers to automatically create/update aliases
        when they successfully identify a user in a game message.
        
        Args:
            telegram_id: User's Telegram ID
            game_name: Name found in game message
            game_source: Source game (gdcards, shmalala, etc.)
            confidence_score: Confidence of the match
        
        Returns:
            Created/updated UserAlias or None if user not found
        """
        # Find user by telegram_id
        user = self.session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return None
        
        # Add or update alias
        return self.add_alias(
            user_id=user.id,
            alias_value=game_name,
            alias_type="game_name",
            game_source=game_source,
            confidence_score=confidence_score
        )
