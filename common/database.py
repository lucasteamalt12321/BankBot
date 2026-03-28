"""Общий модуль базы данных.

Re-export из database/database.py и database/connection.py.

Использование:
    from common.database import Base, get_db, SessionLocal
    from common.database import User, Transaction
"""

from database.database import (
    Base,
    SessionLocal,
    get_db,
    create_tables,
    User,
    UserAlias,
    Transaction,
    ParsedTransaction,
    ShopCategory,
    ShopItem,
    UserPurchase,
    ParsingRule,
    Achievement,
    UserAchievement,
    UserNotification,
    Friendship,
    Gift,
    Clan,
    ClanMember,
    GameSession,
    GamePlayer,
    DndSession,
    DndCharacter,
    DndDiceRoll,
    DndQuest,
    ScheduledTask,
    PurchaseRecord,
    BotBalance,
)
from database.connection import get_connection, get_pooled_engine as get_engine

__all__ = [
    "Base",
    "SessionLocal",
    "get_db",
    "create_tables",
    "get_connection",
    "get_engine",
    # Models
    "User",
    "UserAlias",
    "Transaction",
    "ParsedTransaction",
    "ShopCategory",
    "ShopItem",
    "UserPurchase",
    "ParsingRule",
    "Achievement",
    "UserAchievement",
    "UserNotification",
    "Friendship",
    "Gift",
    "Clan",
    "ClanMember",
    "GameSession",
    "GamePlayer",
    "DndSession",
    "DndCharacter",
    "DndDiceRoll",
    "DndQuest",
    "ScheduledTask",
    "PurchaseRecord",
    "BotBalance",
]
