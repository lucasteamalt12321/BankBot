"""Dependency Injection container for the application."""

from typing import Optional, Dict, Any, Type
from sqlalchemy.orm import Session

from database.database import SessionLocal
from core.repositories import UserRepository
from core.repositories.balance_repository import BalanceRepository
from core.repositories.transaction_repository import TransactionRepository
from core.services import (
    UserService, TransactionService, AdminService, 
    ShopService, BroadcastService, AdminStatsService
)
from core.services.balance_service import BalanceService

class DIContainer:
    """
    Simple dependency injection container.
    
    Manages the creation and lifecycle of services and repositories.
    """
    
    def __init__(self):
        self._session: Optional[Session] = None
        self._instances: Dict[Type, Any] = {}
        self._factories: Dict[Type, callable] = {}
        
        # Register default factories
        self._register_default_factories()
    
    def _register_default_factories(self):
        """Register default factories for core components."""
        self.register_factory(Session, self._create_session)
        self.register_factory(UserRepository, self._create_user_repository)
        self.register_factory(BalanceRepository, self._create_balance_repository)
        self.register_factory(TransactionRepository, self._create_transaction_repository)
        self.register_factory(UserService, self._create_user_service)
        self.register_factory(BalanceService, self._create_balance_service)
        self.register_factory(TransactionService, self._create_transaction_service)
        self.register_factory(AdminService, self._create_admin_service)
        self.register_factory(ShopService, self._create_shop_service)
        self.register_factory(BroadcastService, self._create_broadcast_service)
        self.register_factory(AdminStatsService, self._create_admin_stats_service)
    
    def register_factory(self, interface: Type, factory: callable):
        """
        Register a factory function for an interface.
        
        Args:
            interface: The interface type
            factory: Factory function that returns an instance
        """
        self._factories[interface] = factory
    
    def get(self, interface: Type) -> Any:
        """
        Get an instance of the specified interface.
        
        Args:
            interface: The interface type
            
        Returns:
            Instance of the interface
        """
        if interface not in self._instances:
            if interface not in self._factories:
                raise ValueError(f"No factory registered for {interface}")
            self._instances[interface] = self._factories[interface]()
        
        return self._instances[interface]
    
    def reset(self):
        """Reset all cached instances."""
        self._instances.clear()
    
    def close(self):
        """Close the container and cleanup resources."""
        if self._session:
            self._session.close()
        self.reset()
    
    # Factory methods
    def _create_session(self) -> Session:
        """Create database session."""
        if self._session is None:
            self._session = SessionLocal()
        return self._session
    
    def _create_user_repository(self) -> UserRepository:
        """Create user repository."""
        session = self.get(Session)
        return UserRepository(session)
    
    def _create_balance_repository(self) -> BalanceRepository:
        """Create balance repository."""
        session = self.get(Session)
        return BalanceRepository(session)

    def _create_transaction_repository(self) -> TransactionRepository:
        """Create transaction repository."""
        session = self.get(Session)
        return TransactionRepository(session)

    def _create_user_service(self) -> UserService:
        """Create user service."""
        user_repo = self.get(UserRepository)
        return UserService(user_repo)
    
    def _create_transaction_service(self) -> TransactionService:
        """Create transaction service."""
        user_repo = self.get(UserRepository)
        return TransactionService(user_repo)
    
    def _create_admin_service(self) -> AdminService:
        """Create admin service."""
        user_repo = self.get(UserRepository)
        return AdminService(user_repo)
    
    def _create_shop_service(self) -> ShopService:
        """Create shop service."""
        session = self.get(Session)
        return ShopService(session)
    
    def _create_broadcast_service(self) -> BroadcastService:
        """Create broadcast service."""
        session = self.get(Session)
        return BroadcastService(session)
    
    def _create_admin_stats_service(self) -> AdminStatsService:
        """Create admin stats service."""
        session = self.get(Session)
        return AdminStatsService(session)

    def _create_balance_service(self) -> BalanceService:
        """Create balance service."""
        session = self.get(Session)
        return BalanceService(session)


# Global container instance
_container: Optional[DIContainer] = None

def get_container() -> DIContainer:
    """Get the global DI container."""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container

def reset_container():
    """Reset the global DI container."""
    global _container
    if _container:
        _container.close()
    _container = None