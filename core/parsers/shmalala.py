"""
Парсеры для Shmalala
"""

from typing import Optional
from decimal import Decimal
from .base import BaseParser, AccrualResult, ParserError


class ShmalalaFishingParser(BaseParser):
    """Парсер рыбалки Shmalala"""
    
    def __init__(self):
        super().__init__("Shmalala")
    
    def can_parse(self, text: str) -> bool:
        return "🎣 [Рыбалка] 🎣" in text
    
    def parse(self, text: str) -> Optional[AccrualResult]:
        # Извлекаем имя рыбака
        fisher_name = self.extract_field(text, "Рыбак:")
        if not fisher_name:
            raise ParserError("Fisher name not found in fishing message")
        
        # Извлекаем монеты
        coins_str = self.extract_field(text, "Монеты:")
        if not coins_str:
            raise ParserError("Coins not found in fishing message")
        
        coins = self.extract_number(coins_str, prefix="+")
        if coins is None:
            raise ParserError("Invalid coins value in fishing message")
        
        return AccrualResult(
            game=self.game_name,
            player_name=fisher_name,
            amount=coins,
            accrual_type="fishing",
            raw_message=text
        )


class ShmalalaKarmaParser(BaseParser):
    """Парсер кармы Shmalala"""
    
    def __init__(self):
        super().__init__("Shmalala Karma")
    
    def can_parse(self, text: str) -> bool:
        return "Лайк! Вы повысили рейтинг пользователя" in text
    
    def parse(self, text: str) -> Optional[AccrualResult]:
        lines = text.splitlines()
        player_name = None
        
        # Ищем строку с лайком
        for line in lines:
            if "Лайк! Вы повысили рейтинг пользователя" in line:
                parts = line.split("пользователя")
                if len(parts) > 1:
                    player_name = parts[1].strip().rstrip('.').strip()
                    break
        
        if not player_name:
            raise ParserError("Player name not found in karma message")
        
        # Карма всегда +1 (игнорируем "Теперь его рейтинг:")
        return AccrualResult(
            game=self.game_name,
            player_name=player_name,
            amount=Decimal("1"),
            accrual_type="karma",
            raw_message=text
        )
