"""
Простая система парсинга сообщений от Shmalala
Основана на логике построчного анализа сообщений
"""

import structlog
from typing import Optional, Dict
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class ParsedFishing:
    """Результат парсинга рыбалки"""
    fisher_name: str
    coins: int
    raw_message: str


@dataclass
class ParsedCard:
    """Результат парсинга новой карты"""
    player_name: str
    points: int
    raw_message: str


class SimpleShmalalaParser:
    """Простой парсер для сообщений Shmalala и GD Cards"""
    
    def parse_card_message(self, text: str) -> Optional[ParsedCard]:
        """
        Парсит сообщение о новой карте из GD Cards
        
        Args:
            text: Текст сообщения
            
        Returns:
            ParsedCard если сообщение распознано, None иначе
        """
        # Проверяем, что это сообщение о новой карте
        if "🃏 НОВАЯ КАРТА 🃏" not in text:
            return None
        
        lines = text.splitlines()
        player_name = None
        points = None
        
        for line in lines:
            line = line.strip()
            
            # Ищем игрока
            if "Игрок:" in line:
                try:
                    _, user = line.split(":", 1)
                    player_name = user.strip()
                    logger.debug(f"Найден игрок: {player_name}")
                except ValueError:
                    logger.warning(f"Не удалось извлечь имя игрока из строки: {line}")
                    continue
            
            # Ищем очки
            if "Очки:" in line and "+" in line:
                try:
                    _, n = line.split("+", 1)
                    points = int(n.strip())
                    logger.debug(f"Найдены очки: {points}")
                except (ValueError, IndexError):
                    logger.warning(f"Не удалось извлечь очки из строки: {line}")
                    continue
        
        # Если удалось найти и игрока, и очки
        if player_name and points is not None:
            result = ParsedCard(
                player_name=player_name,
                points=points,
                raw_message=text[:200]  # Сохраняем первые 200 символов для отладки
            )
            
            logger.info(
                "Сообщение о новой карте успешно распознано",
                player=player_name,
                points=points
            )
            
            return result
        else:
            logger.debug(
                "Не удалось полностью распознать сообщение о карте",
                player_found=player_name is not None,
                points_found=points is not None
            )
            return None
    
    def parse_fishing_message(self, text: str) -> Optional[ParsedFishing]:
        """
        Парсит сообщение рыбалки от Shmalala
        
        Args:
            text: Текст сообщения
            
        Returns:
            ParsedFishing если сообщение распознано, None иначе
        """
        # Проверяем, что это сообщение рыбалки
        if "🎣 [Рыбалка] 🎣" not in text:
            return None
        
        lines = text.splitlines()
        fisher_name = None
        coins = None
        
        for line in lines:
            line = line.strip()
            
            # Ищем рыбака
            if "Рыбак:" in line:
                try:
                    _, fisher = line.split(":", 1)
                    fisher_name = fisher.strip()
                    logger.debug(f"Найден рыбак: {fisher_name}")
                except ValueError:
                    logger.warning(f"Не удалось извлечь имя рыбака из строки: {line}")
                    continue
            
            # Ищем монеты
            if "Монеты:" in line and "+" in line:
                try:
                    _, a = line.split("+", 1)
                    n, _ = a.split("(", 1)
                    coins = int(n.strip())
                    logger.debug(f"Найдены монеты: {coins}")
                except (ValueError, IndexError):
                    logger.warning(f"Не удалось извлечь монеты из строки: {line}")
                    continue
        
        # Если удалось найти и рыбака, и монеты
        if fisher_name and coins is not None:
            result = ParsedFishing(
                fisher_name=fisher_name,
                coins=coins,
                raw_message=text[:200]  # Сохраняем первые 200 символов для отладки
            )
            
            logger.info(
                "Сообщение рыбалки успешно распознано",
                fisher=fisher_name,
                coins=coins
            )
            
            return result
        else:
            logger.debug(
                "Не удалось полностью распознать сообщение рыбалки",
                fisher_found=fisher_name is not None,
                coins_found=coins is not None
            )
            return None


def parse_shmalala_message(text: str) -> Optional[ParsedFishing]:
    """
    Удобная функция для парсинга сообщений Shmalala
    
    Args:
        text: Текст сообщения
        
    Returns:
        ParsedFishing если сообщение распознано, None иначе
    """
    parser = SimpleShmalalaParser()
    return parser.parse_fishing_message(text)


def parse_card_message(text: str) -> Optional[ParsedCard]:
    """
    Удобная функция для парсинга сообщений о картах GD Cards
    
    Args:
        text: Текст сообщения
        
    Returns:
        ParsedCard если сообщение распознано, None иначе
    """
    parser = SimpleShmalalaParser()
    return parser.parse_card_message(text)


def parse_game_message(text: str) -> Optional[Dict]:
    """
    Универсальная функция для парсинга игровых сообщений
    Автоматически определяет тип сообщения и парсит его
    
    Args:
        text: Текст сообщения
        
    Returns:
        Словарь с результатами парсинга или None
    """
    parser = SimpleShmalalaParser()
    
    # Пробуем распарсить как карту
    card_result = parser.parse_card_message(text)
    if card_result:
        return {
            'type': 'card',
            'user': card_result.player_name,
            'amount': card_result.points,
            'data': card_result
        }
    
    # Пробуем распарсить как рыбалку
    fishing_result = parser.parse_fishing_message(text)
    if fishing_result:
        return {
            'type': 'fishing',
            'user': fishing_result.fisher_name,
            'amount': fishing_result.coins,
            'data': fishing_result
        }
    
    return None


# Алиас для обратной совместимости
parse_fishing_message = parse_shmalala_message