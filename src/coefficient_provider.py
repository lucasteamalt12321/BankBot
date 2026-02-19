"""Coefficient provider for game-specific conversion rates."""

import json
from typing import Dict


class CoefficientProvider:
    """Provides game-specific conversion coefficients."""
    
    def __init__(self, coefficients: Dict[str, int]):
        """
        Initialize with coefficient mapping.
        
        Args:
            coefficients: Dict mapping game name to coefficient
        """
        self.coefficients = coefficients
    
    def get_coefficient(self, game: str) -> int:
        """
        Get coefficient for a game.
        
        Args:
            game: Game name
            
        Returns:
            Coefficient value
            
        Raises:
            ValueError: If game not found in configuration
        """
        if game not in self.coefficients:
            raise ValueError(f"No coefficient configured for game: {game}")
        return self.coefficients[game]
    
    @classmethod
    def from_config(cls, config_path: str) -> 'CoefficientProvider':
        """
        Load coefficients from JSON config file.
        
        Args:
            config_path: Path to JSON configuration file
            
        Returns:
            New CoefficientProvider instance
        """
        with open(config_path, 'r') as f:
            coefficients = json.load(f)
        return cls(coefficients)
