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
    orbs: int  # Орбы за дроп
    raw_message: str


@dataclass
class ParsedProfile:
    """Результат парсинга профиля GDcards"""
    player_name: str
    orbs: int
    points: int
    raw_message: str


@dataclass
class ParsedOrbDrop:
    """Результат парсинга начисления орбов (сундук, награда и т.д.)"""
    player_name: str
    orbs: int
    raw_message: str


class SimpleShmalalaParser:
    """Простой парсер для сообщений Shmalala и GD Cards"""
    
    def parse_profile_message(self, text: str) -> Optional[ParsedProfile]:
        """
        Парсит сообщение профиля из GD Cards
        
        Args:
            text: Текст сообщения
            
        Returns:
            ParsedProfile если сообщение распознано, None иначе
        """
        # Проверяем, что это сообщение профиля
        if "ПРОФИЛЬ" not in text and "Профиль" not in text:
            return None
        
        lines = text.splitlines()
        player_name = None
        orbs = None
        points = None
        
        for line in lines:
            line = line.strip()
            
            # Ищем имя игрока в первой строке с "ПРОФИЛЬ" или "Профиль"
            if "ПРОФИЛЬ" in line or "Профиль" in line:
                try:
                    # Пробуем разные варианты
                    if "ПРОФИЛЬ" in line:
                        parts = line.split("ПРОФИЛЬ")
                    else:
                        parts = line.split("Профиль")
                    
                    if len(parts) > 1:
                        player_name = parts[1].strip()
                        # Убираем разделители
                        player_name = player_name.replace("─", "").strip()
                        if player_name:  # Проверяем, что имя не пустое
                            logger.debug(f"Найден игрок в профиле: {player_name}")
                except Exception as e:
                    logger.warning(f"Не удалось извлечь имя игрока из строки: {line}, ошибка: {e}")
                    continue
            
            # Ищем ник (альтернативный способ найти имя игрока)
            if "Ник:" in line and not player_name:
                try:
                    _, nick_part = line.split("Ник:", 1)
                    player_name = nick_part.strip()
                    logger.debug(f"Найден игрок через ник: {player_name}")
                except Exception as e:
                    logger.warning(f"Не удалось извлечь ник из строки: {line}, ошибка: {e}")
                    continue
            
            # Ищем орбы
            if "Орбы:" in line or "Орбы :" in line:
                try:
                    if "Орбы:" in line:
                        _, orb_part = line.split("Орбы:", 1)
                    else:
                        _, orb_part = line.split("Орбы :", 1)
                    # Извлекаем число до пробела или скобки
                    orb_str = orb_part.strip().split()[0]
                    orbs = int(orb_str)
                    logger.debug(f"Найдены орбы: {orbs}")
                except (ValueError, IndexError) as e:
                    logger.warning(f"Не удалось извлечь орбы из строки: {line}, ошибка: {e}")
                    continue
            
            # Ищем очки
            if "Очки:" in line or "Очки :" in line:
                try:
                    if "Очки:" in line:
                        _, points_part = line.split("Очки:", 1)
                    else:
                        _, points_part = line.split("Очки :", 1)
                    # Извлекаем число до пробела или скобки
                    points_str = points_part.strip().split()[0]
                    points = int(points_str)
                    logger.debug(f"Найдены очки: {points}")
                except (ValueError, IndexError) as e:
                    logger.warning(f"Не удалось извлечь очки из строки: {line}, ошибка: {e}")
                    continue
        
        # Если удалось найти игрока и хотя бы орбы или очки
        if player_name and (orbs is not None or points is not None):
            # Если орбы не найдены, ставим 0
            if orbs is None:
                orbs = 0
            # Если очки не найдены, ставим 0
            if points is None:
                points = 0
                
            result = ParsedProfile(
                player_name=player_name,
                orbs=orbs,
                points=points,
                raw_message=text[:200]  # Сохраняем первые 200 символов для отладки
            )
            
            logger.info(
                "Сообщение профиля GDcards успешно распознано",
                player=player_name,
                orbs=orbs,
                points=points
            )
            
            return result
        else:
            logger.debug(
                "Не удалось полностью распознать сообщение профиля",
                player_found=player_name is not None,
                orbs_found=orbs is not None,
                points_found=points is not None,
                text_preview=text[:100]
            )
            return None
    
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
        orbs = None
        
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
            
            # Ищем орбы за дроп
            if "Орбы за дроп:" in line and "+" in line:
                try:
                    _, n = line.split("+", 1)
                    orbs = int(n.strip())
                    logger.debug(f"Найдены орбы за дроп: {orbs}")
                except (ValueError, IndexError):
                    logger.warning(f"Не удалось извлечь орбы из строки: {line}")
                    continue
        
        # Если удалось найти игрока и хотя бы очки или орбы
        if player_name and (points is not None or orbs is not None):
            # Если очки не найдены, ставим 0
            if points is None:
                points = 0
            # Если орбы не найдены, ставим 0
            if orbs is None:
                orbs = 0
            
            result = ParsedCard(
                player_name=player_name,
                points=points,
                orbs=orbs,
                raw_message=text[:200]  # Сохраняем первые 200 символов для отладки
            )
            
            logger.info(
                "Сообщение о новой карте успешно распознано",
                player=player_name,
                points=points,
                orbs=orbs
            )
            
            return result
        else:
            logger.debug(
                "Не удалось полностью распознать сообщение о карте",
                player_found=player_name is not None,
                points_found=points is not None,
                orbs_found=orbs is not None
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
    
    def parse_orb_drop_message(self, text: str) -> Optional[ParsedOrbDrop]:
        """
        Парсит сообщение о начислении орбов (сундук, награда и т.д.)
        
        Args:
            text: Текст сообщения
            
        Returns:
            ParsedOrbDrop если сообщение распознано, None иначе
        """
        # Проверяем различные форматы начисления орбов
        # Формат 1: "Username открыл сундук и получил X орб"
        # Формат 2: "Username получил X орбов"
        
        if "орб" not in text.lower():
            return None
        
        lines = text.splitlines()
        player_name = None
        orbs = None
        
        # Пробуем найти в первой строке
        first_line = lines[0] if lines else text
        
        # Паттерн: "Username открыл сундук и получил X орб"
        if "открыл сундук" in first_line or "получил" in first_line:
            try:
                # Извлекаем имя игрока (до "открыл" или "получил")
                if "открыл" in first_line:
                    player_name = first_line.split("открыл")[0].strip()
                elif "получил" in first_line:
                    player_name = first_line.split("получил")[0].strip()
                
                # Извлекаем количество орбов
                import re
                orb_match = re.search(r'(\d+)\s*орб', first_line)
                if orb_match:
                    orbs = int(orb_match.group(1))
                    
                logger.debug(f"Найдено начисление орбов: {player_name} получил {orbs} орбов")
                
            except (ValueError, IndexError) as e:
                logger.warning(f"Не удалось распарсить начисление орбов: {first_line}, ошибка: {e}")
                return None
        
        # Если удалось найти и игрока, и орбы
        if player_name and orbs is not None:
            result = ParsedOrbDrop(
                player_name=player_name,
                orbs=orbs,
                raw_message=text[:200]
            )
            
            logger.info(
                "Сообщение о начислении орбов успешно распознано",
                player=player_name,
                orbs=orbs
            )
            
            return result
        else:
            logger.debug(
                "Не удалось полностью распознать сообщение о начислении орбов",
                player_found=player_name is not None,
                orbs_found=orbs is not None
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
    
    # Пробуем распарсить как профиль GDcards
    profile_result = parser.parse_profile_message(text)
    if profile_result:
        # Для профиля не начисляем очки автоматически, просто информируем
        logger.info(
            "Распознан профиль GDcards (информационное сообщение)",
            player=profile_result.player_name,
            orbs=profile_result.orbs,
            points=profile_result.points
        )
        # Возвращаем None, чтобы не начислять очки за просмотр профиля
        return None
    
    # Пробуем распарсить как карту
    card_result = parser.parse_card_message(text)
    if card_result:
        return {
            'type': 'card',
            'user': card_result.player_name,
            'amount': card_result.points,
            'orbs': card_result.orbs if hasattr(card_result, 'orbs') else 0,
            'data': card_result
        }
    
    # Пробуем распарсить как начисление орбов (сундук и т.д.)
    orb_drop_result = parser.parse_orb_drop_message(text)
    if orb_drop_result:
        return {
            'type': 'orb_drop',
            'user': orb_drop_result.player_name,
            'amount': 0,  # Орбы не дают очков напрямую
            'orbs': orb_drop_result.orbs,
            'data': orb_drop_result
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