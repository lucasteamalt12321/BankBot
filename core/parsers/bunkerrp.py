"""
Парсеры для Bunker RP
"""

from typing import Optional
from .base import BaseParser, ProfileResult, GameEndResult, ParserError


class BunkerRPProfileParser(BaseParser):
    """Парсер профилей Bunker RP"""
    
    def __init__(self):
        super().__init__("Bunker RP")
    
    def can_parse(self, text: str) -> bool:
        return "👤" in text and "💵 Деньги:" in text and "Bunker" in text
    
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
            raise ParserError("Player name not found in bunker profile")
        
        # Извлекаем деньги
        money_str = self.extract_field(text, "💵 Деньги:")
        if not money_str:
            raise ParserError("Money not found in bunker profile")
        
        money = self.extract_number(money_str, prefix="")
        if money is None:
            raise ParserError("Invalid money value in bunker profile")
        
        return ProfileResult(
            game=self.game_name,
            player_name=player_name,
            balance=money,
            raw_message=text
        )


class BunkerRPGameEndParser(BaseParser):
    """Парсер окончания игры Bunker RP"""
    
    def __init__(self):
        super().__init__("Bunker RP")
    
    def can_parse(self, text: str) -> bool:
        return "Прошли в бункер:" in text
    
    def parse(self, text: str) -> Optional[GameEndResult]:
        lines = text.splitlines()
        winners = []
        in_winners_section = False
        
        for line in lines:
            if "Прошли в бункер:" in line:
                in_winners_section = True
                continue
            elif "Не прошли в бункер:" in line:
                in_winners_section = False
                break
            
            if in_winners_section:
                line_stripped = line.strip()
                # Строки начинаются с номера
                if line_stripped and line_stripped[0].isdigit() and ". " in line_stripped:
                    player_name = line_stripped.split(". ", 1)[1].strip()
                    if player_name:
                        winners.append(player_name)
        
        if not winners:
            raise ParserError("No winners found in bunker game end message")
        
        return GameEndResult(
            game=self.game_name,
            player_name=winners[0],  # Первый победитель как основной
            winners=winners,
            raw_message=text
        )
