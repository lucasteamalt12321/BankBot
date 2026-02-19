"""
Парсеры для True Mafia
"""

from typing import Optional
from decimal import Decimal
from .base import BaseParser, ProfileResult, GameEndResult, ParserError


class TrueMafiaProfileParser(BaseParser):
    """Парсер профилей True Mafia"""
    
    def __init__(self):
        super().__init__("True Mafia")
    
    def can_parse(self, text: str) -> bool:
        return "👤" in text and "💵 Деньги:" in text
    
    def parse(self, text: str) -> Optional[ProfileResult]:
        lines = text.splitlines()
        player_name = None
        
        # Извлекаем имя игрока из строки с 👤
        for line in lines:
            if "👤" in line:
                parts = line.split("👤")
                if len(parts) > 1:
                    player_name = parts[1].strip()
                    break
        
        if not player_name:
            raise ParserError("Player name not found in mafia profile")
        
        # Извлекаем деньги
        money_str = self.extract_field(text, "💵 Деньги:")
        if not money_str:
            raise ParserError("Money not found in mafia profile")
        
        money = self.extract_number(money_str, prefix="")
        if money is None:
            raise ParserError("Invalid money value in mafia profile")
        
        return ProfileResult(
            game=self.game_name,
            player_name=player_name,
            balance=money,
            raw_message=text
        )


class TrueMafiaGameEndParser(BaseParser):
    """Парсер окончания игры True Mafia"""
    
    def __init__(self):
        super().__init__("True Mafia")
    
    def can_parse(self, text: str) -> bool:
        return "Победители:" in text
    
    def parse(self, text: str) -> Optional[GameEndResult]:
        lines = text.splitlines()
        winners = []
        in_winners_section = False
        
        for line in lines:
            if "Победители:" in line:
                in_winners_section = True
                continue
            elif "Остальные участники:" in line:
                in_winners_section = False
                break
            
            if in_winners_section and line.strip():
                # Извлекаем имя игрока до дефиса
                if " - " in line:
                    player_name = line.split(" - ")[0].strip()
                    if player_name:
                        winners.append(player_name)
        
        if not winners:
            raise ParserError("No winners found in mafia game end message")
        
        return GameEndResult(
            game=self.game_name,
            player_name=winners[0],  # Первый победитель как основной
            winners=winners,
            raw_message=text
        )
