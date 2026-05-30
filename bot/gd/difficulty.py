"""GD Module difficulty logic."""
from database.database import get_db_session, Level, PlayerStats, LevelCompletion
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def is_level_eligible(level_id: int, user_id: int) -> tuple[bool, str]:
    """
    Check if user is eligible to submit a level.
    
    Rules:
    - User can submit any level from top-100
    - User can submit their current hardest level
    - User can submit the next level after their hardest (position - 1)
    
    Returns:
        tuple[bool, str]: (is_eligible, reason)
    """
    try:
        with get_db_session() as session:
            # Get the level
            level = session.query(Level).filter_by(id=level_id).first()
            if not level:
                return False, "Уровень не найден в базе данных"
            
            # Check if level is in top-100
            if level.position > 100:
                return False, f"Уровень '{level.name}' не входит в топ-100 (позиция: {level.position})"
            
            # Get player stats
            player_stats = session.query(PlayerStats).filter_by(user_id=user_id).first()
            
            # If no stats, user can only submit levels from position 100
            if not player_stats or not player_stats.hardest_level_id:
                if level.position == 100:
                    return True, "Первое прохождение — можно начать с позиции 100"
                else:
                    return False, "Начните с уровня на позиции 100"
            
            # Get hardest level
            hardest_level = session.query(Level).filter_by(id=player_stats.hardest_level_id).first()
            if not hardest_level:
                return False, "Ошибка: хардест не найден"
            
            # Check if level is easier or equal to hardest
            if level.position >= hardest_level.position:
                return True, f"Уровень доступен (ваш хардест: {hardest_level.name}, позиция {hardest_level.position})"
            
            # Check if level is the next harder level (position - 1)
            if level.position == hardest_level.position - 1:
                return True, f"Следующий уровень после вашего хардеста (позиция {level.position})"
            
            # Level is too hard
            return False, f"Уровень слишком сложный. Ваш хардест: {hardest_level.name} (позиция {hardest_level.position}). Доступны уровни с позиции {hardest_level.position - 1} и выше."
            
    except Exception as e:
        logger.error(f"Error checking level eligibility: {e}")
        return False, "Ошибка при проверке доступности уровня"


def update_hardest_level(user_id: int, level_id: int) -> bool:
    """
    Update user's hardest level if the new level is harder.
    
    Args:
        user_id: User ID
        level_id: Level ID
        
    Returns:
        bool: True if hardest was updated, False otherwise
    """
    try:
        with get_db_session() as session:
            # Get player stats
            player_stats = session.query(PlayerStats).filter_by(user_id=user_id).first()
            if not player_stats:
                player_stats = PlayerStats(user_id=user_id, total_approved=0)
                session.add(player_stats)
            
            # Get the new level
            new_level = session.query(Level).filter_by(id=level_id).first()
            if not new_level:
                return False
            
            # If no hardest, set this as hardest
            if not player_stats.hardest_level_id:
                player_stats.hardest_level_id = level_id
                session.commit()
                logger.info(f"Set first hardest for user {user_id}: {new_level.name} (position {new_level.position})")
                return True
            
            # Get current hardest
            current_hardest = session.query(Level).filter_by(id=player_stats.hardest_level_id).first()
            if not current_hardest:
                player_stats.hardest_level_id = level_id
                session.commit()
                return True
            
            # Update if new level is harder (lower position number)
            if new_level.position < current_hardest.position:
                player_stats.hardest_level_id = level_id
                session.commit()
                logger.info(
                    f"Updated hardest for user {user_id}: "
                    f"{current_hardest.name} (pos {current_hardest.position}) → "
                    f"{new_level.name} (pos {new_level.position})"
                )
                return True
            
            return False
            
    except Exception as e:
        logger.error(f"Error updating hardest level: {e}")
        return False


def get_user_hardest(user_id: int) -> Optional[Level]:
    """
    Get user's hardest level.
    
    Args:
        user_id: User ID
        
    Returns:
        Level or None
    """
    try:
        with get_db_session() as session:
            player_stats = session.query(PlayerStats).filter_by(user_id=user_id).first()
            if not player_stats or not player_stats.hardest_level_id:
                return None
            
            hardest_level = session.query(Level).filter_by(id=player_stats.hardest_level_id).first()
            return hardest_level
            
    except Exception as e:
        logger.error(f"Error getting user hardest: {e}")
        return None


def get_eligible_levels(user_id: int) -> list[Level]:
    """
    Get list of levels eligible for user to submit.
    
    Args:
        user_id: User ID
        
    Returns:
        List of eligible levels
    """
    try:
        with get_db_session() as session:
            player_stats = session.query(PlayerStats).filter_by(user_id=user_id).first()
            
            # If no stats, only position 100 is eligible
            if not player_stats or not player_stats.hardest_level_id:
                return session.query(Level).filter_by(position=100).all()
            
            # Get hardest level
            hardest_level = session.query(Level).filter_by(id=player_stats.hardest_level_id).first()
            if not hardest_level:
                return []
            
            # Get all levels from (hardest.position - 1) to 100
            eligible_levels = (
                session.query(Level)
                .filter(Level.position >= hardest_level.position - 1)
                .filter(Level.position <= 100)
                .order_by(Level.position)
                .all()
            )
            
            return eligible_levels
            
    except Exception as e:
        logger.error(f"Error getting eligible levels: {e}")
        return []


def calculate_difficulty_score(level: Level) -> int:
    """
    Calculate difficulty score for a level.
    Lower position = higher score.
    
    Args:
        level: Level object
        
    Returns:
        Difficulty score (1-100)
    """
    return 101 - level.position
