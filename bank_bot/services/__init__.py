"""Service layer — re-export из core/services/."""

from core.services import (
    AdminService,
    AdminStatsService,
    BalanceService,
    BroadcastService,
    ShopService,
    TransactionService,
    UserService,
)

# alias_service не в __init__ core/services, импортируем напрямую
from core.services.alias_service import AliasService

__all__ = [
    "AdminService",
    "AdminStatsService",
    "AliasService",
    "BalanceService",
    "BroadcastService",
    "ShopService",
    "TransactionService",
    "UserService",
]
