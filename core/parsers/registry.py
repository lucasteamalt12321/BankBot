"""
Реестр и фабрика парсеров
"""

from typing import List, Optional
from .base import BaseParser, ParseResult
from .gdcards import GDCardsProfileParser, GDCardsCardParser, GDCardsOrbDropParser
from .shmalala import ShmalalaFishingParser, ShmalalaKarmaParser
from .truemafia import TrueMafiaProfileParser, TrueMafiaGameEndParser
from .bunkerrp import BunkerRPProfileParser, BunkerRPGameEndParser
import structlog

logger = structlog.get_logger()


class ParserRegistry:
    """Реестр всех парсеров"""
    
    def __init__(self):
        self.parsers: List[BaseParser] = []
        self._register_default_parsers()
    
    def _register_default_parsers(self):
        """Регистрирует стандартные парсеры"""
        # GD Cards
        self.register(GDCardsProfileParser())
        self.register(GDCardsCardParser())
        self.register(GDCardsOrbDropParser())
        
        # Shmalala
        self.register(ShmalalaFishingParser())
        self.register(ShmalalaKarmaParser())
        
        # True Mafia
        self.register(TrueMafiaProfileParser())
        self.register(TrueMafiaGameEndParser())
        
        # Bunker RP
        self.register(BunkerRPProfileParser())
        self.register(BunkerRPGameEndParser())
        
        logger.info(
            "Parser registry initialized",
            total_parsers=len(self.parsers)
        )
    
    def register(self, parser: BaseParser):
        """
        Регистрирует парсер
        
        Args:
            parser: Экземпляр парсера
        """
        self.parsers.append(parser)
        logger.debug(
            "Parser registered",
            parser=parser.__class__.__name__,
            game=parser.game_name
        )
    
    def parse(self, text: str) -> Optional[ParseResult]:
        """
        Пытается распарсить сообщение всеми зарегистрированными парсерами
        
        Args:
            text: Текст сообщения
            
        Returns:
            ParseResult или None если ни один парсер не смог обработать
        """
        for parser in self.parsers:
            try:
                result = parser.safe_parse(text)
                if result:
                    logger.info(
                        "Message parsed successfully",
                        parser=parser.__class__.__name__,
                        game=result.game,
                        player=result.player_name
                    )
                    return result
            except Exception as e:
                logger.error(
                    "Parser failed",
                    parser=parser.__class__.__name__,
                    error=str(e)
                )
                continue
        
        logger.warning(
            "No parser could handle message",
            text_preview=text[:100]
        )
        return None
    
    def get_parsers_for_game(self, game: str) -> List[BaseParser]:
        """
        Возвращает все парсеры для конкретной игры
        
        Args:
            game: Название игры
            
        Returns:
            Список парсеров
        """
        return [p for p in self.parsers if p.game_name == game]


# Глобальный экземпляр реестра
_registry = None


def get_registry() -> ParserRegistry:
    """Возвращает глобальный реестр парсеров"""
    global _registry
    if _registry is None:
        _registry = ParserRegistry()
    return _registry


def parse_message(text: str) -> Optional[ParseResult]:
    """
    Удобная функция для парсинга сообщений
    
    Args:
        text: Текст сообщения
        
    Returns:
        ParseResult или None
    """
    registry = get_registry()
    return registry.parse(text)
