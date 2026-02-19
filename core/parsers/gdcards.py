"""
Парсеры для GD Cards
"""

from typing import Optional
from decimal import Decimal
from .base import BaseParser, ProfileResult, AccrualResult, ParserError


class GDCardsProfileParser(BaseParser):
    """Парсер профилей GD Cards"""
    
    def __init__(self):
        super().__init__("GD Cards")
    
    def can_parse(self, text: str) -> bool:
        return "ПРОФИЛЬ" in text or "Профиль" in text
    
    def parse(self, text: str) -> Optional[ProfileResult]:
        lines = text.splitlines()
        player_name = None
        orbs = None
        
        # Извлекаем имя игрока
        for line in lines:
            if "ПРОФИЛЬ" in line or "Профиль" in line:
                parts = line.split("ПРОФИЛЬ" if "ПРОФИЛЬ" in line else "Профиль")
                if len(parts) > 1:
                    player_name = parts[1].strip().replace("─", "").strip()
                    if player_name:
                        break
        
        # Альтернативный способ - через "Ник:"
        if not player_name:
            player_name = self.extract_field(text, "Ник:")
        
        if not player_name:
            raise ParserError("Player name not found in profile")
        
        # Извлекаем орбы
        orbs_str = self.extract_field(text, "Орбы:")
        if not orbs_str:
            orbs_str = self.extract_field(text, "Орбы :")
        
        if orbs_str:
            orbs = self.extract_number(orbs_str, prefix="")
        
        if orbs is None:
            raise ParserError("Orbs not found in profile")
        
        return ProfileResult(
            game=self.game_name,
            player_name=player_name,
            balance=orbs,
            raw_message=text
        )


class GDCardsCardParser(BaseParser):
    """Парсер новых карт GD Cards"""
    
    def __init__(self):
        super().__init__("GD Cards")
    
    def can_parse(self, text: str) -> bool:
        return "🃏 НОВАЯ КАРТА 🃏" in text
    
    def parse(self, text: str) -> Optional[AccrualResult]:
        # Извлекаем имя игрока
        player_name = self.extract_field(text, "Игрок:")
        if not player_name:
            raise ParserError("Player name not found in card message")
        
        # Извлекаем орбы за дроп
        orbs_str = self.extract_field(text, "Орбы за дроп:")
        orbs = None
        if orbs_str:
            orbs = self.extract_number(orbs_str, prefix="+")
        
        if orbs is None or orbs == 0:
            # Если орбов нет, пробуем очки
            points_str = self.extract_field(text, "Очки:")
            if points_str:
                orbs = self.extract_number(points_str, prefix="+")
        
        if orbs is None:
            raise ParserError("Neither orbs nor points found in card message")
        
        return AccrualResult(
            game=self.game_name,
            player_name=player_name,
            amount=orbs,
            accrual_type="card",
            raw_message=text
        )


class GDCardsOrbDropParser(BaseParser):
    """Парсер начислений орбов (сундуки, награды)"""
    
    def __init__(self):
        super().__init__("GD Cards")
    
    def can_parse(self, text: str) -> bool:
        return "орб" in text.lower() and ("открыл сундук" in text or "получил" in text)
    
    def parse(self, text: str) -> Optional[AccrualResult]:
        import re
        
        first_line = text.splitlines()[0] if text.splitlines() else text
        
        # Извлекаем имя игрока
        player_name = None
        if "открыл" in first_line:
            player_name = first_line.split("открыл")[0].strip()
        elif "получил" in first_line:
            player_name = first_line.split("получил")[0].strip()
        
        if not player_name:
            raise ParserError("Player name not found in orb drop message")
        
        # Извлекаем количество орбов
        orb_match = re.search(r'(\d+)\s*орб', first_line)
        if not orb_match:
            raise ParserError("Orbs amount not found in orb drop message")
        
        orbs = Decimal(orb_match.group(1))
        
        return AccrualResult(
            game=self.game_name,
            player_name=player_name,
            amount=orbs,
            accrual_type="orb_drop",
            raw_message=text
        )
