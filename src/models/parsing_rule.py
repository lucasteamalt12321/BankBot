"""ParsingRule model for storing parsing configuration."""

from sqlalchemy import Column, Integer, String, Float, Boolean, JSON
from database.database import Base


class ParsingRule(Base):
    """
    Model for storing parsing rules configuration.
    
    This model replaces the coefficients.json file approach and provides
    a database-backed configuration for parsing rules.
    
    This is the new unified parsing configuration model that will replace
    the old ParsingRule model in database.py during the migration.
    
    Attributes:
        id: Primary key
        game_name: Unique name of the game (e.g., 'gdcards', 'shmalala')
        parser_class: Name of the parser class to use
        coefficient: Multiplier coefficient for points calculation
        enabled: Whether this parsing rule is active
        config: Additional JSON configuration for the parser
    """
    __tablename__ = 'parsing_rules_config'
    
    id = Column(Integer, primary_key=True)
    game_name = Column(String, unique=True, nullable=False)
    parser_class = Column(String, nullable=False)
    coefficient = Column(Float, default=1.0)
    enabled = Column(Boolean, default=True)
    config = Column(JSON, default={})
    
    def __repr__(self):
        return (
            f"<ParsingRule(id={self.id}, game_name='{self.game_name}', "
            f"parser_class='{self.parser_class}', coefficient={self.coefficient}, "
            f"enabled={self.enabled})>"
        )
