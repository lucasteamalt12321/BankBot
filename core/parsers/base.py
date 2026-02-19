"""
Базовые классы для системы парсинга игровых сообщений
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from decimal import Decimal
import structlog

logger = structlog.get_logger()


class ParserError(Exception):
    """Ошибка парсинга сообщения"""
    pass


@dataclass
class ParseResult:
    """Базовый результат парсинга"""
    game: str
    player_name: str
    raw_message: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать в словарь"""
        return {
            'game': self.game,
            'player_name': self.player_name,
            'raw_message': self.raw_message[:200]
        }


@dataclass
class ProfileResult(ParseResult):
    """Результат парсинга профиля"""
    balance: Decimal  # Основная валюта игры
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result['type'] = 'profile'
        result['balance'] = float(self.balance)
        return result


@dataclass
class AccrualResult(ParseResult):
    """Результат парсинга начисления"""
    amount: Decimal  # Количество начисленной валюты
    accrual_type: str  # Тип начисления (card, fishing, win, etc.)
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result['type'] = 'accrual'
        result['amount'] = float(self.amount)
        result['accrual_type'] = self.accrual_type
        return result


@dataclass
class GameEndResult(ParseResult):
    """Результат парсинга окончания игры"""
    winners: list  # Список победителей
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result['type'] = 'game_end'
        result['winners'] = self.winners
        return result


class BaseParser(ABC):
    """Базовый класс для всех парсеров"""
    
    def __init__(self, game_name: str):
        self.game_name = game_name
        self.logger = logger.bind(parser=self.__class__.__name__, game=game_name)
    
    @abstractmethod
    def can_parse(self, text: str) -> bool:
        """
        Проверяет, может ли парсер обработать это сообщение
        
        Args:
            text: Текст сообщения
            
        Returns:
            True если парсер может обработать сообщение
        """
        pass
    
    @abstractmethod
    def parse(self, text: str) -> Optional[ParseResult]:
        """
        Парсит сообщение
        
        Args:
            text: Текст сообщения
            
        Returns:
            ParseResult или None если не удалось распарсить
            
        Raises:
            ParserError: При критической ошибке парсинга
        """
        pass
    
    def safe_parse(self, text: str) -> Optional[ParseResult]:
        """
        Безопасный парсинг с обработкой ошибок
        
        Args:
            text: Текст сообщения
            
        Returns:
            ParseResult или None
        """
        try:
            if not self.can_parse(text):
                return None
            
            result = self.parse(text)
            
            if result:
                self.logger.info(
                    "Message parsed successfully",
                    player=result.player_name,
                    type=result.__class__.__name__
                )
            
            return result
            
        except ParserError as e:
            self.logger.error(
                "Parser error",
                error=str(e),
                text_preview=text[:100]
            )
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error during parsing",
                error=str(e),
                error_type=type(e).__name__,
                text_preview=text[:100]
            )
            return None
    
    def extract_field(self, text: str, field_name: str, separator: str = ":") -> Optional[str]:
        """
        Извлекает значение поля из текста
        
        Args:
            text: Текст сообщения
            field_name: Название поля
            separator: Разделитель (по умолчанию ":")
            
        Returns:
            Значение поля или None
        """
        lines = text.splitlines()
        
        for line in lines:
            if field_name in line:
                parts = line.split(separator, 1)
                if len(parts) > 1:
                    return parts[1].strip()
        
        return None
    
    def extract_number(self, text: str, prefix: str = "+") -> Optional[Decimal]:
        """
        Извлекает число из текста
        
        Args:
            text: Текст
            prefix: Префикс перед числом (например "+")
            
        Returns:
            Decimal или None
        """
        try:
            if prefix and text.startswith(prefix):
                text = text[len(prefix):]
            
            # Убираем все кроме цифр, точки и минуса
            cleaned = ''.join(c for c in text.split()[0] if c.isdigit() or c in '.-')
            
            if cleaned:
                return Decimal(cleaned)
        except Exception as e:
            self.logger.warning(
                "Failed to extract number",
                text=text,
                error=str(e)
            )
        
        return None
