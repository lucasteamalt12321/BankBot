"""Base repository pattern for database operations using SQLAlchemy."""

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeclarativeMeta

T = TypeVar('T', bound=DeclarativeMeta)


class BaseRepository(Generic[T]):
    """
    Generic base repository providing CRUD operations for SQLAlchemy models.
    
    This repository implements the Repository pattern to abstract database
    operations and provide a consistent interface for data access.
    
    Type Parameters:
        T: SQLAlchemy model class (must inherit from DeclarativeMeta)
    
    Example:
        >>> from database.database import User, SessionLocal
        >>> session = SessionLocal()
        >>> user_repo = BaseRepository(User, session)
        >>> user = user_repo.get(1)
        >>> all_users = user_repo.get_all()
    """
    
    def __init__(self, model: Type[T], session: Session):
        """
        Initialize repository with model and database session.
        
        Args:
            model: SQLAlchemy model class
            session: SQLAlchemy database session
        """
        self.model = model
        self.session = session
    
    def get(self, id: int) -> Optional[T]:
        """
        Get a single record by primary key ID.
        
        Args:
            id: Primary key value
            
        Returns:
            Model instance if found, None otherwise
            
        Example:
            >>> user = repo.get(1)
            >>> if user:
            ...     print(user.username)
        """
        return self.session.query(self.model).filter_by(id=id).first()
    
    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[T]:
        """
        Get all records with optional pagination.
        
        Args:
            limit: Maximum number of records to return (None for all)
            offset: Number of records to skip
            
        Returns:
            List of model instances
            
        Example:
            >>> # Get first 10 users
            >>> users = repo.get_all(limit=10)
            >>> # Get next 10 users
            >>> users = repo.get_all(limit=10, offset=10)
        """
        query = self.session.query(self.model)
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()
    
    def get_by(self, **filters) -> Optional[T]:
        """
        Get a single record matching the given filters.
        
        Args:
            **filters: Field name and value pairs to filter by
            
        Returns:
            First matching model instance, or None if not found
            
        Example:
            >>> user = repo.get_by(username="john_doe")
            >>> user = repo.get_by(telegram_id=123456789)
        """
        return self.session.query(self.model).filter_by(**filters).first()
    
    def filter(self, **filters) -> List[T]:
        """
        Get all records matching the given filters.
        
        Args:
            **filters: Field name and value pairs to filter by
            
        Returns:
            List of matching model instances
            
        Example:
            >>> active_users = repo.filter(is_active=True)
            >>> admin_users = repo.filter(is_admin=True)
        """
        return self.session.query(self.model).filter_by(**filters).all()
    
    def create(self, **kwargs) -> T:
        """
        Create a new record.
        
        Args:
            **kwargs: Field names and values for the new record
            
        Returns:
            Created model instance
            
        Raises:
            SQLAlchemyError: If database operation fails
            
        Example:
            >>> user = repo.create(
            ...     username="john_doe",
            ...     telegram_id=123456789,
            ...     balance=0
            ... )
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.commit()
        self.session.refresh(instance)
        return instance
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """
        Update an existing record by ID.
        
        Args:
            id: Primary key of the record to update
            **kwargs: Field names and new values
            
        Returns:
            Updated model instance if found, None otherwise
            
        Example:
            >>> user = repo.update(1, balance=100, is_vip=True)
        """
        instance = self.get(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.session.commit()
            self.session.refresh(instance)
        return instance
    
    def delete(self, id: int) -> bool:
        """
        Delete a record by ID.
        
        Args:
            id: Primary key of the record to delete
            
        Returns:
            True if record was deleted, False if not found
            
        Example:
            >>> if repo.delete(1):
            ...     print("User deleted")
            ... else:
            ...     print("User not found")
        """
        instance = self.get(id)
        if instance:
            self.session.delete(instance)
            self.session.commit()
            return True
        return False
    
    def count(self, **filters) -> int:
        """
        Count records matching the given filters.
        
        Args:
            **filters: Optional field name and value pairs to filter by
            
        Returns:
            Number of matching records
            
        Example:
            >>> total_users = repo.count()
            >>> active_users = repo.count(is_active=True)
        """
        query = self.session.query(self.model)
        if filters:
            query = query.filter_by(**filters)
        return query.count()
    
    def exists(self, **filters) -> bool:
        """
        Check if any record exists matching the given filters.
        
        Args:
            **filters: Field name and value pairs to filter by
            
        Returns:
            True if at least one matching record exists, False otherwise
            
        Example:
            >>> if repo.exists(username="john_doe"):
            ...     print("Username already taken")
        """
        return self.session.query(
            self.session.query(self.model).filter_by(**filters).exists()
        ).scalar()
    
    def bulk_create(self, items: List[Dict[str, Any]]) -> List[T]:
        """
        Create multiple records in a single transaction.
        
        Args:
            items: List of dictionaries with field names and values
            
        Returns:
            List of created model instances
            
        Example:
            >>> users = repo.bulk_create([
            ...     {"username": "user1", "balance": 0},
            ...     {"username": "user2", "balance": 0},
            ... ])
        """
        instances = [self.model(**item) for item in items]
        self.session.bulk_save_objects(instances, return_defaults=True)
        self.session.commit()
        return instances
