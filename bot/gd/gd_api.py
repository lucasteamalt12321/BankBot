"""
Geometry Dash API integration using direct HTTP requests.

This module provides functions to fetch user and level data from Geometry Dash servers
without relying on the gd.py library (which has installation issues).
"""

import aiohttp
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# GD Server endpoints
GD_BASE_URL = "http://www.boomlings.com/database"
GD_USER_ENDPOINT = f"{GD_BASE_URL}/getGJUsers20.php"
GD_LEVEL_ENDPOINT = f"{GD_BASE_URL}/downloadGJLevel22.php"

# Game version constants
GAME_VERSION = "22"
BINARY_VERSION = "42"
SECRET = "Wmfd2893gb7"


async def get_user_info(username: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user information from Geometry Dash servers.
    
    Args:
        username: GD username to search for
        
    Returns:
        Dictionary with user data or None if not found
        
    Example response:
        {
            'account_id': '12345',
            'user_id': '67890',
            'username': 'Player',
            'stars': 1234,
            'demons': 56,
            'creator_points': 10,
            'coins': 789,
            'user_coins': 45,
            'diamonds': 123,
            'rank': 1000
        }
    """
    params = {
        "str": username,
        "total": 0,
        "page": 0,
        "gameVersion": GAME_VERSION,
        "binaryVersion": BINARY_VERSION,
        "secret": SECRET
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GD_USER_ENDPOINT, data=params) as response:
                if response.status != 200:
                    logger.error(f"GD API returned status {response.status} for user {username}")
                    return None
                
                text = await response.text()
                
                # GD API returns "-1" if user not found
                if text == "-1":
                    logger.info(f"User {username} not found in GD")
                    return None
                
                # Parse response (format: key:value:key:value...)
                return _parse_user_response(text)
                
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching GD user {username}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching GD user {username}: {e}")
        return None


async def get_level_info(level_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch level information from Geometry Dash servers.
    
    Args:
        level_id: GD level ID
        
    Returns:
        Dictionary with level data or None if not found
        
    Example response:
        {
            'level_id': '12345',
            'name': 'Bloodbath',
            'description': 'Extreme demon',
            'version': 2,
            'creator_id': '67890',
            'creator_name': 'Riot',
            'difficulty': 10,
            'demon_difficulty': 6,
            'stars': 10,
            'downloads': 1000000,
            'likes': 50000,
            'length': 2,
            'coins': 0,
            'verified_coins': False
        }
    """
    params = {
        "levelID": level_id,
        "gameVersion": GAME_VERSION,
        "binaryVersion": BINARY_VERSION,
        "secret": SECRET
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GD_LEVEL_ENDPOINT, data=params) as response:
                if response.status != 200:
                    logger.error(f"GD API returned status {response.status} for level {level_id}")
                    return None
                
                text = await response.text()
                
                # GD API returns "-1" if level not found
                if text == "-1":
                    logger.info(f"Level {level_id} not found in GD")
                    return None
                
                # Parse response
                return _parse_level_response(text)
                
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching GD level {level_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching GD level {level_id}: {e}")
        return None


def _parse_user_response(response: str) -> Dict[str, Any]:
    """
    Parse GD user API response.
    
    Response format: key:value:key:value...
    
    Key mapping:
    1: username
    2: user_id
    3: stars
    4: demons
    6: rank (global)
    8: creator_points
    13: coins
    14: icon_type
    16: account_id
    17: user_coins
    46: diamonds
    """
    parts = response.split(":")
    data = {}
    
    # Parse key-value pairs
    for i in range(0, len(parts) - 1, 2):
        key = parts[i]
        value = parts[i + 1]
        
        if key == "1":
            data["username"] = value
        elif key == "2":
            data["user_id"] = value
        elif key == "3":
            data["stars"] = int(value)
        elif key == "4":
            data["demons"] = int(value)
        elif key == "6":
            data["rank"] = int(value) if value != "0" else None
        elif key == "8":
            data["creator_points"] = int(value)
        elif key == "13":
            data["coins"] = int(value)
        elif key == "16":
            data["account_id"] = value
        elif key == "17":
            data["user_coins"] = int(value)
        elif key == "46":
            data["diamonds"] = int(value)
    
    return data


def _parse_level_response(response: str) -> Dict[str, Any]:
    """
    Parse GD level API response.
    
    Response format: key:value:key:value...#hash#seed
    
    Key mapping:
    1: level_id
    2: name
    3: description (base64)
    5: version
    6: creator_id
    9: difficulty
    10: downloads
    12: official_song_id
    13: game_version
    14: likes
    15: length
    17: demon (0/1)
    18: stars
    19: featured
    25: auto (0/1)
    27: password
    28: upload_date
    29: update_date
    30: original_level_id
    35: custom_song_id
    37: coins
    38: verified_coins (0/1)
    39: stars_requested
    43: demon_difficulty (3=easy, 4=medium, 5=hard, 6=insane, 7=extreme)
    """
    # Split by hash separator
    main_data = response.split("#")[0]
    parts = main_data.split(":")
    data = {}
    
    # Parse key-value pairs
    for i in range(0, len(parts) - 1, 2):
        key = parts[i]
        value = parts[i + 1]
        
        if key == "1":
            data["level_id"] = value
        elif key == "2":
            data["name"] = value
        elif key == "3":
            # Description is base64 encoded, but we'll skip decoding for now
            data["description"] = value
        elif key == "5":
            data["version"] = int(value)
        elif key == "6":
            data["creator_id"] = value
        elif key == "9":
            data["difficulty"] = int(value)
        elif key == "10":
            data["downloads"] = int(value)
        elif key == "14":
            data["likes"] = int(value)
        elif key == "15":
            data["length"] = int(value)
        elif key == "17":
            data["is_demon"] = value == "1"
        elif key == "18":
            data["stars"] = int(value)
        elif key == "37":
            data["coins"] = int(value)
        elif key == "38":
            data["verified_coins"] = value == "1"
        elif key == "43":
            data["demon_difficulty"] = int(value) if value else None
    
    return data


def format_user_stats(user_data: Dict[str, Any]) -> str:
    """
    Format user data into a readable message.
    
    Args:
        user_data: Dictionary from get_user_info()
        
    Returns:
        Formatted string for Telegram message
    """
    username = user_data.get("username", "Unknown")
    stars = user_data.get("stars", 0)
    demons = user_data.get("demons", 0)
    creator_points = user_data.get("creator_points", 0)
    coins = user_data.get("coins", 0)
    user_coins = user_data.get("user_coins", 0)
    diamonds = user_data.get("diamonds", 0)
    rank = user_data.get("rank")
    
    msg = f"📊 **Статистика игрока {username}**\n\n"
    msg += f"⭐ Звёзды: {stars}\n"
    msg += f"👹 Демоны: {demons}\n"
    msg += f"🏆 Creator Points: {creator_points}\n"
    msg += f"🪙 Монеты: {coins}\n"
    msg += f"💎 User Coins: {user_coins}\n"
    msg += f"💠 Алмазы: {diamonds}\n"
    
    if rank:
        msg += f"🌍 Глобальный ранг: #{rank}\n"
    
    return msg


def format_level_info(level_data: Dict[str, Any]) -> str:
    """
    Format level data into a readable message.
    
    Args:
        level_data: Dictionary from get_level_info()
        
    Returns:
        Formatted string for Telegram message
    """
    name = level_data.get("name", "Unknown")
    level_id = level_data.get("level_id", "?")
    stars = level_data.get("stars", 0)
    downloads = level_data.get("downloads", 0)
    likes = level_data.get("likes", 0)
    is_demon = level_data.get("is_demon", False)
    demon_difficulty = level_data.get("demon_difficulty")
    length = level_data.get("length", 0)
    coins = level_data.get("coins", 0)
    
    # Length mapping
    length_names = {
        0: "Tiny",
        1: "Short",
        2: "Medium",
        3: "Long",
        4: "XL"
    }
    
    # Demon difficulty mapping
    demon_names = {
        3: "Easy Demon",
        4: "Medium Demon",
        5: "Hard Demon",
        6: "Insane Demon",
        7: "Extreme Demon"
    }
    
    msg = f"🎮 **{name}** (ID: {level_id})\n\n"
    
    if is_demon and demon_difficulty:
        msg += f"👹 Сложность: {demon_names.get(demon_difficulty, 'Demon')}\n"
    else:
        msg += f"⭐ Звёзды: {stars}\n"
    
    msg += f"📏 Длина: {length_names.get(length, 'Unknown')}\n"
    msg += f"📥 Скачивания: {downloads:,}\n"
    msg += f"👍 Лайки: {likes:,}\n"
    
    if coins > 0:
        msg += f"🪙 Монеты: {coins}\n"
    
    return msg
