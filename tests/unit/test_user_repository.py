"""Unit tests for UserRepository specialized methods."""

import pytest
from datetime import datetime, timedelta
from database.database import SessionLocal, User, Base, create_engine
from src.repository.user_repository import UserRepository
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing."""
    engine = sa_create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def user_repository(session):
    """Create a UserRepository instance."""
    return UserRepository(User, session)


@pytest.fixture
def sample_users(session):
    """Create sample users for testing."""
    users = [
        User(
            telegram_id=100001,
            username="admin_user",
            first_name="Admin",
            balance=5000,
            is_admin=True,
            is_vip=False,
            last_activity=datetime.utcnow()
        ),
        User(
            telegram_id=100002,
            username="vip_user",
            first_name="VIP",
            balance=3000,
            is_admin=False,
            is_vip=True,
            vip_until=datetime.utcnow() + timedelta(days=30),
            last_activity=datetime.utcnow() - timedelta(hours=2)
        ),
        User(
            telegram_id=100003,
            username="expired_vip",
            first_name="Expired",
            balance=1000,
            is_admin=False,
            is_vip=True,
            vip_until=datetime.utcnow() - timedelta(days=1),
            last_activity=datetime.utcnow() - timedelta(days=5)
        ),
        User(
            telegram_id=100004,
            username="rich_user",
            first_name="Rich",
            balance=10000,
            total_earned=15000,
            is_admin=False,
            is_vip=False,
            last_activity=datetime.utcnow() - timedelta(hours=1)
        ),
        User(
            telegram_id=100005,
            username="poor_user",
            first_name="Poor",
            balance=50,
            total_earned=100,
            is_admin=False,
            is_vip=False,
            sticker_unlimited=True,
            sticker_unlimited_until=datetime.utcnow() - timedelta(hours=1),
            last_activity=datetime.utcnow() - timedelta(days=10)
        ),
    ]
    
    for user in users:
        session.add(user)
    session.commit()
    
    return users


class TestUserRepositoryBasicMethods:
    """Test basic UserRepository methods."""
    
    def test_get_by_telegram_id(self, user_repository, sample_users):
        """Test getting user by Telegram ID."""
        user = user_repository.get_by_telegram_id(100001)
        assert user is not None
        assert user.username == "admin_user"
        assert user.telegram_id == 100001
    
    def test_get_by_telegram_id_not_found(self, user_repository, sample_users):
        """Test getting non-existent user by Telegram ID."""
        user = user_repository.get_by_telegram_id(999999)
        assert user is None
    
    def test_get_by_username(self, user_repository, sample_users):
        """Test getting user by username."""
        user = user_repository.get_by_username("vip_user")
        assert user is not None
        assert user.telegram_id == 100002
        assert user.is_vip is True
    
    def test_get_by_username_not_found(self, user_repository, sample_users):
        """Test getting non-existent user by username."""
        user = user_repository.get_by_username("nonexistent")
        assert user is None
    
    def test_get_or_create_existing(self, user_repository, sample_users):
        """Test get_or_create with existing user."""
        initial_count = user_repository.count_total_users()
        user = user_repository.get_or_create(
            telegram_id=100001,
            username="should_not_create"
        )
        assert user.username == "admin_user"  # Original username
        assert user_repository.count_total_users() == initial_count
    
    def test_get_or_create_new(self, user_repository, sample_users):
        """Test get_or_create with new user."""
        initial_count = user_repository.count_total_users()
        user = user_repository.get_or_create(
            telegram_id=200001,
            username="new_user",
            first_name="New"
        )
        assert user.username == "new_user"
        assert user.telegram_id == 200001
        assert user_repository.count_total_users() == initial_count + 1


class TestUserRepositoryAdminMethods:
    """Test admin-related methods."""
    
    def test_get_all_admins(self, user_repository, sample_users):
        """Test getting all admin users."""
        admins = user_repository.get_all_admins()
        assert len(admins) == 1
        assert admins[0].username == "admin_user"
        assert admins[0].is_admin is True
    
    def test_count_admins(self, user_repository, sample_users):
        """Test counting admin users."""
        count = user_repository.count_admins()
        assert count == 1


class TestUserRepositoryVIPMethods:
    """Test VIP-related methods."""
    
    def test_get_all_vips(self, user_repository, sample_users):
        """Test getting all VIP users."""
        vips = user_repository.get_all_vips()
        assert len(vips) == 2  # vip_user and expired_vip
        usernames = [vip.username for vip in vips]
        assert "vip_user" in usernames
        assert "expired_vip" in usernames
    
    def test_count_vips(self, user_repository, sample_users):
        """Test counting VIP users."""
        count = user_repository.count_vips()
        assert count == 2
    
    def test_get_users_with_expired_vip(self, user_repository, sample_users):
        """Test getting users with expired VIP."""
        now = datetime.utcnow()
        expired_vips = user_repository.get_users_with_expired_vip(now)
        assert len(expired_vips) == 1
        assert expired_vips[0].username == "expired_vip"
        assert expired_vips[0].vip_until < now


class TestUserRepositoryBalanceMethods:
    """Test balance-related methods."""
    
    def test_get_users_with_balance_above(self, user_repository, sample_users):
        """Test getting users with balance above threshold."""
        users = user_repository.get_users_with_balance_above(2000)
        assert len(users) == 3  # admin_user, vip_user, rich_user
        balances = [user.balance for user in users]
        assert all(balance >= 2000 for balance in balances)
    
    def test_get_users_with_balance_above_high_threshold(self, user_repository, sample_users):
        """Test getting users with high balance threshold."""
        users = user_repository.get_users_with_balance_above(5000)
        assert len(users) == 2  # admin_user, rich_user
    
    def test_get_top_users_by_balance(self, user_repository, sample_users):
        """Test getting top users by balance."""
        top_users = user_repository.get_top_users_by_balance(3)
        assert len(top_users) == 3
        assert top_users[0].username == "rich_user"
        assert top_users[0].balance == 10000
        assert top_users[1].username == "admin_user"
        assert top_users[1].balance == 5000
        assert top_users[2].username == "vip_user"
        assert top_users[2].balance == 3000
    
    def test_get_top_users_by_earnings(self, user_repository, sample_users):
        """Test getting top users by total earnings."""
        top_earners = user_repository.get_top_users_by_earnings(3)
        assert len(top_earners) == 3
        assert top_earners[0].username == "rich_user"
        assert top_earners[0].total_earned == 15000
    
    def test_bulk_update_balance(self, user_repository, sample_users):
        """Test bulk balance update."""
        # Get user IDs for admin_user and vip_user
        admin = user_repository.get_by_username("admin_user")
        vip = user_repository.get_by_username("vip_user")
        
        initial_admin_balance = admin.balance
        initial_vip_balance = vip.balance
        
        # Update balances
        updated = user_repository.bulk_update_balance([admin.id, vip.id], 500)
        assert updated == 2
        
        # Verify updates
        user_repository.session.refresh(admin)
        user_repository.session.refresh(vip)
        assert admin.balance == initial_admin_balance + 500
        assert vip.balance == initial_vip_balance + 500
    
    def test_bulk_update_balance_negative(self, user_repository, sample_users):
        """Test bulk balance update with negative amount."""
        admin = user_repository.get_by_username("admin_user")
        initial_balance = admin.balance
        
        updated = user_repository.bulk_update_balance([admin.id], -1000)
        assert updated == 1
        
        user_repository.session.refresh(admin)
        assert admin.balance == initial_balance - 1000


class TestUserRepositoryActivityMethods:
    """Test activity-related methods."""
    
    def test_get_active_users_since(self, user_repository, sample_users):
        """Test getting active users since datetime."""
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_users = user_repository.get_active_users_since(yesterday)
        
        # Should get admin_user, vip_user, and rich_user
        assert len(active_users) >= 3
        usernames = [user.username for user in active_users]
        assert "admin_user" in usernames
        assert "vip_user" in usernames
        assert "rich_user" in usernames
        assert "poor_user" not in usernames  # Last active 10 days ago
    
    def test_get_active_users_since_recent(self, user_repository, sample_users):
        """Test getting very recent active users."""
        one_hour_ago = datetime.utcnow() - timedelta(hours=1, minutes=30)
        active_users = user_repository.get_active_users_since(one_hour_ago)
        
        # Should get admin_user and rich_user
        assert len(active_users) >= 2
        usernames = [user.username for user in active_users]
        assert "admin_user" in usernames
        assert "rich_user" in usernames


class TestUserRepositoryStickerMethods:
    """Test sticker-related methods."""
    
    def test_get_users_with_expired_stickers(self, user_repository, sample_users):
        """Test getting users with expired sticker access."""
        now = datetime.utcnow()
        expired_stickers = user_repository.get_users_with_expired_stickers(now)
        
        assert len(expired_stickers) == 1
        assert expired_stickers[0].username == "poor_user"
        assert expired_stickers[0].sticker_unlimited is True
        assert expired_stickers[0].sticker_unlimited_until < now


class TestUserRepositoryCountMethods:
    """Test counting methods."""
    
    def test_count_total_users(self, user_repository, sample_users):
        """Test counting total users."""
        count = user_repository.count_total_users()
        assert count == 5
    
    def test_count_total_users_empty(self, user_repository, session):
        """Test counting users in empty database."""
        count = user_repository.count_total_users()
        assert count == 0


class TestUserRepositoryEdgeCases:
    """Test edge cases and error handling."""
    
    def test_get_top_users_limit_exceeds_total(self, user_repository, sample_users):
        """Test getting top users when limit exceeds total users."""
        top_users = user_repository.get_top_users_by_balance(100)
        assert len(top_users) == 5  # Only 5 users exist
    
    def test_bulk_update_empty_list(self, user_repository, sample_users):
        """Test bulk update with empty user list."""
        updated = user_repository.bulk_update_balance([], 100)
        assert updated == 0
    
    def test_bulk_update_nonexistent_ids(self, user_repository, sample_users):
        """Test bulk update with non-existent user IDs."""
        updated = user_repository.bulk_update_balance([999999, 888888], 100)
        assert updated == 0
    
    def test_get_users_with_balance_above_zero(self, user_repository, sample_users):
        """Test getting users with balance above 0."""
        users = user_repository.get_users_with_balance_above(0)
        assert len(users) == 5  # All users have positive balance
