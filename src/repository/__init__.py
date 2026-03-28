"""Repository layer for database access."""

from src.repository.base import BaseRepository
from src.repository.user_repository import UserRepository
from src.repository.unit_of_work import UnitOfWork

# Re-export legacy SQLiteRepository from src/repository_impl.py for backward compatibility
from src.repository_impl import SQLiteRepository, DatabaseRepository  # noqa: F401

__all__ = ["BaseRepository", "UserRepository", "UnitOfWork", "SQLiteRepository", "DatabaseRepository"]
