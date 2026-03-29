"""Единый унифицированный парсер для всех форматов игровых сообщений.

Этот модуль является центральной точкой входа для всей системы парсинга.
Все форматы входных данных поддерживаются через единый интерфейс.

Поддерживаемые форматы:
- GD Cards: профили, новые карты, начисления орбов
- Shmalala: рыбалка, карма
- True Mafia: профили, окончание игры
- Bunker RP: профили, окончание игры

Использование::

    from core.parsers.unified import UnifiedParser, parse

    # Через экземпляр
    parser = UnifiedParser()
    result = parser.parse(message_text)

    # Через удобную функцию
    result = parse(message_text)
"""

from typing import Optional

from .base import (
    BaseParser,
    ParseResult,
    ProfileResult,
    AccrualResult,
    GameEndResult,
    ParserError,
)
from .gdcards import GDCardsProfileParser, GDCardsCardParser, GDCardsOrbDropParser
from .shmalala import ShmalalaFishingParser, ShmalalaKarmaParser
from .truemafia import TrueMafiaProfileParser, TrueMafiaGameEndParser
from .bunkerrp import BunkerRPProfileParser, BunkerRPGameEndParser

__all__ = [
    "UnifiedParser",
    "parse",
    # Re-export base types for convenience
    "BaseParser",
    "ParseResult",
    "ProfileResult",
    "AccrualResult",
    "GameEndResult",
    "ParserError",
    # Re-export concrete parsers
    "GDCardsProfileParser",
    "GDCardsCardParser",
    "GDCardsOrbDropParser",
    "ShmalalaFishingParser",
    "ShmalalaKarmaParser",
    "TrueMafiaProfileParser",
    "TrueMafiaGameEndParser",
    "BunkerRPProfileParser",
    "BunkerRPGameEndParser",
]


class UnifiedParser:
    """Единый парсер, объединяющий все форматы игровых сообщений.

    Перебирает зарегистрированные парсеры в порядке приоритета и возвращает
    результат первого успешного парсинга.

    Порядок проверки:
    1. GD Cards (карты, орбы, профили)
    2. Shmalala (рыбалка, карма)
    3. True Mafia (окончание игры, профили)
    4. Bunker RP (окончание игры, профили)

    Пример::

        parser = UnifiedParser()
        result = parser.parse(text)
        if result:
            print(result.game, result.player_name)
    """

    def __init__(self) -> None:
        self._parsers: list[BaseParser] = [
            # GD Cards — специфичные форматы первыми
            GDCardsCardParser(),
            GDCardsOrbDropParser(),
            GDCardsProfileParser(),
            # Shmalala
            ShmalalaFishingParser(),
            ShmalalaKarmaParser(),
            # True Mafia
            TrueMafiaGameEndParser(),
            TrueMafiaProfileParser(),
            # Bunker RP
            BunkerRPGameEndParser(),
            BunkerRPProfileParser(),
        ]

    def parse(self, text: str) -> Optional[ParseResult]:
        """Распарсить сообщение, перебирая все зарегистрированные парсеры.

        Args:
            text: Текст сообщения для парсинга.

        Returns:
            ParseResult (ProfileResult, AccrualResult или GameEndResult)
            если сообщение распознано, иначе None.
        """
        for parser in self._parsers:
            result = parser.safe_parse(text)
            if result is not None:
                return result
        return None

    def can_parse(self, text: str) -> bool:
        """Проверить, может ли хотя бы один парсер обработать сообщение.

        Args:
            text: Текст сообщения.

        Returns:
            True если сообщение может быть распознано.
        """
        return any(p.can_parse(text) for p in self._parsers)


# Глобальный экземпляр для удобного использования
_unified_parser: Optional[UnifiedParser] = None


def _get_parser() -> UnifiedParser:
    """Получить глобальный экземпляр UnifiedParser (lazy singleton)."""
    global _unified_parser
    if _unified_parser is None:
        _unified_parser = UnifiedParser()
    return _unified_parser


def parse(text: str) -> Optional[ParseResult]:
    """Удобная функция для парсинга игровых сообщений.

    Эквивалентна ``UnifiedParser().parse(text)``, но использует
    глобальный singleton для экономии ресурсов.

    Args:
        text: Текст сообщения.

    Returns:
        ParseResult если сообщение распознано, иначе None.

    Example::

        from core.parsers.unified import parse
        result = parse(message_text)
        if isinstance(result, AccrualResult):
            print(f"{result.player_name} получил {result.amount}")
    """
    return _get_parser().parse(text)
