"""Реестр и фабрика парсеров.

Конфигурация парсеров хранится в таблице `parsing_rules` БД.
Поддерживает горячую перезагрузку без перезапуска бота через reload().
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
    """Реестр всех парсеров.

    Конфигурация (коэффициенты, активность) хранится в таблице parsing_rules.
    Вызов reload() применяет изменения из БД без перезапуска бота.
    """

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
    
    def reload(self) -> None:
        """Перезагрузить конфигурацию парсеров из БД без перезапуска бота.

        Читает активные правила из таблицы parsing_rules и обновляет
        коэффициенты зарегистрированных парсеров.
        """
        try:
            from database.database import get_db, ParsingRule
            db = next(get_db())
            try:
                rules = db.query(ParsingRule).filter(
                    ParsingRule.is_active == True  # noqa: E712
                ).all()
                rule_map = {r.bot_name: float(r.multiplier) for r in rules}
                for parser in self.parsers:
                    if parser.game_name in rule_map:
                        parser.coefficient = rule_map[parser.game_name]
                        logger.debug(
                            "Parser coefficient updated from DB",
                            parser=parser.__class__.__name__,
                            coefficient=parser.coefficient,
                        )
                logger.info("ParserRegistry reloaded from DB", rules_loaded=len(rules))
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to reload ParserRegistry from DB", error=str(e))

    def get_config_from_db(self) -> dict:
        """Получить текущую конфигурацию парсеров из БД.

        Returns:
            Словарь {bot_name: {multiplier, currency_type, is_active}}.
        """
        try:
            from database.database import get_db, ParsingRule
            db = next(get_db())
            try:
                rules = db.query(ParsingRule).all()
                return {
                    r.bot_name: {
                        "multiplier": float(r.multiplier),
                        "currency_type": r.currency_type,
                        "is_active": r.is_active,
                    }
                    for r in rules
                }
            finally:
                db.close()
        except Exception as e:
            logger.error("Failed to get config from DB", error=str(e))
            return {}

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
