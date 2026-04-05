"""Base repository classes with proper SQLAlchemy integration."""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, List
from sqlalchemy.orm import Session

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    """Abstract base repository with SQLAlchemy session."""

    def __init__(self, session: Session):
        self.session = session

    @abstractmethod
    def get(self, id: int) -> Optional[T]:
        """Get entity by ID."""
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """Get all entities."""
        pass

    @abstractmethod
    def create(self, entity: T) -> T:
        """Create new entity."""
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """Update existing entity."""
        pass

    @abstractmethod
    def delete(self, id: int) -> bool:
        """Delete entity by ID."""
        pass
