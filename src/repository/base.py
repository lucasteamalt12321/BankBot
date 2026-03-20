<<<<<<< HEAD
"""Base repository pattern for database operations using SQLAlchemy."""
=======
"""Base repository with CRUD operations using SQLAlchemy."""
>>>>>>> f1369b8 (chore: minor update, possibly buggy)

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeclarativeMeta

T = TypeVar('T', bound=DeclarativeMeta)


class BaseRepository(Generic[T]):
    """
<<<<<<< HEAD
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
=======
    Базовый репозиторий с CRUD операциями для SQLAlchemy моделей.
    
    Provides standard CRUD operations: create, read, update, delete.
>>>>>>> f1369b8 (chore: minor update, possibly buggy)
    """
    
    def __init__(self, model: Type[T], session: Session):
        """
<<<<<<< HEAD
        Initialize repository with model and database session.
        
        Args:
            model: SQLAlchemy model class
            session: SQLAlchemy database session
=======
        Инициализация репозитория.
        
        Args:
            model: SQLAlchemy модель для работы
            session: SQLAlchemy сессия
>>>>>>> f1369b8 (chore: minor update, possibly buggy)
        """
        self.model = model
        self.session = session
    
    def get(self, id: int) -> Optional[T]:
        """
<<<<<<< HEAD
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
=======
        Получить запись по ID.
        
        Args:
            id: ID записи
            
        Returns:
            Модель или None если не найдена
        """
        return self.session.query(self.model).filter_by(id=id).first()
    
    def get_by(self, **criteria) -> Optional[T]:
        """
        Получить запись по критериям.
        
        Args:
            **criteria: Поля для фильтрации
            
        Returns:
            Модель или None если не найдена
        """
        return self.session.query(self.model).filter_by(**criteria).first()
    
    def get_all(self) -> List[T]:
        """
        Получить все записи.
        
        Returns:
            Список всех моделей
        """
        return self.session.query(self.model).all()
    
    def get_all_by(self, **criteria) -> List[T]:
        """
        Получить все записи по критериям.
        
        Args:
            **criteria: Поля для фильтрации
            
        Returns:
            Список моделей
        """
        return self.session.query(self.model).filter_by(**criteria).all()
    
    def create(self, **kwargs) -> T:
        """
        Создать новую запись.
        
        Args:
            **kwargs: Атрибуты для создания
            
        Returns:
            Созданная модель
>>>>>>> f1369b8 (chore: minor update, possibly buggy)
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.commit()
        self.session.refresh(instance)
        return instance
    
    def update(self, id: int, **kwargs) -> Optional[T]:
        """
<<<<<<< HEAD
        Update an existing record by ID.
        
        Args:
            id: Primary key of the record to update
            **kwargs: Field names and new values
            
        Returns:
            Updated model instance if found, None otherwise
            
        Example:
            >>> user = repo.update(1, balance=100, is_vip=True)
=======
        Обновить запись по ID.
        
        Args:
            id: ID записи
            **kwargs: Атрибуты для обновления
            
        Returns:
            Обновленная модель или None если не найдена
>>>>>>> f1369b8 (chore: minor update, possibly buggy)
        """
        instance = self.get(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.session.commit()
            self.session.refresh(instance)
        return instance
    
<<<<<<< HEAD
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
=======
    def update_by(self, criteria: Dict[str, Any], **kwargs) -> Optional[T]:
        """
        Обновить запись по критериям.
        
        Args:
            criteria: Поля для поиска
            **kwargs: Атрибуты для обновления
            
        Returns:
            Обновленная модель или None если не найдена
        """
        instance = self.get_by(**criteria)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            self.session.commit()
            self.session.refresh(instance)
        return instance
    
    def delete(self, id: int) -> bool:
        """
        Удалить запись по ID.
        
        Args:
            id: ID записи
            
        Returns:
            True если удалена, False если не найдена
>>>>>>> f1369b8 (chore: minor update, possibly buggy)
        """
        instance = self.get(id)
        if instance:
            self.session.delete(instance)
            self.session.commit()
            return True
        return False
    
<<<<<<< HEAD
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
=======
    def delete_by(self, **criteria) -> bool:
        """
        Удалить запись по критериям.
        
        Args:
            **criteria: Поля для поиска
            
        Returns:
            True если удалена, False если не найдена
        """
        instance = self.get_by(**criteria)
        if instance:
            self.session.delete(instance)
            self.session.commit()
            return True
        return False
    
    def exists(self, **criteria) -> bool:
        """
        Проверить существование записи.
        
        Args:
            **criteria: Поля для поиска
            
        Returns:
            True если существует, False если нет
        """
        return self.session.query(self.model).filter_by(**criteria).first() is not None
    
    def count(self, **criteria) -> int:
        """
        Подсчитать количество записей.
        
        Args:
            **criteria: Поля для фильтрации
            
        Returns:
            Количество записей
        """
        return self.session.query(self.model).filter_by(**criteria).count()
>>>>>>> f1369b8 (chore: minor update, possibly buggy)
