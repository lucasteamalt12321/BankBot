"""Unit tests for ShopService implementation."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.services.shop_service import ShopService
from src.repository.user_repository import UserRepository
from database.database import Base, User, ShopCategory, ShopItem, UserPurchase


@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()


@pytest.fixture
def user_repository(in_memory_db):
    """Create a UserRepository instance."""
    return UserRepository(in_memory_db)


@pytest.fixture
def shop_service(user_repository):
    """Create a ShopService instance."""
    return ShopService(user_repository)


class TestShopServiceInitialization:
    """Test ShopService initialization."""

    def test_init_creates_service(self, user_repository):
        """Test that ShopService is created successfully."""
        service = ShopService(user_repository)
        assert service is not None
        assert service.user_repo == user_repository


class TestShopServiceCategoryMethods:
    """Test category management methods."""

    def test_get_all_categories(self, shop_service, in_memory_db):
        """Test getting all categories."""
        categories = [
            ShopCategory(name="Category 1", sort_order=1, is_active=True),
            ShopCategory(name="Category 2", sort_order=2, is_active=True),
            ShopCategory(name="Category 3", sort_order=3, is_active=False),
        ]
        in_memory_db.add_all(categories)
        in_memory_db.commit()

        all_categories = shop_service.get_all_categories()
        assert len(all_categories) == 2  # Only active

        all_categories_including_inactive = shop_service.get_all_categories(only_active=False)
        assert len(all_categories_including_inactive) == 3

    def test_get_category_by_id(self, shop_service, in_memory_db):
        """Test getting a category by ID."""
        category = ShopCategory(name="Test Category", sort_order=1)
        in_memory_db.add(category)
        in_memory_db.commit()

        retrieved = shop_service.get_category_by_id(category.id)
        assert retrieved is not None
        assert retrieved.name == "Test Category"

    def test_get_category_by_id_not_found(self, shop_service):
        """Test getting a non-existent category."""
        category = shop_service.get_category_by_id(999999)
        assert category is None

    def test_get_items_by_category(self, shop_service, in_memory_db):
        """Test getting items by category."""
        category = ShopCategory(name="Test Category", sort_order=1)
        in_memory_db.add(category)
        in_memory_db.commit()

        items = [
            ShopItem(category_id=category.id, name="Item 1", price=100, is_active=True),
            ShopItem(category_id=category.id, name="Item 2", price=200, is_active=True),
            ShopItem(category_id=category.id, name="Item 3", price=300, is_active=False),
        ]
        in_memory_db.add_all(items)
        in_memory_db.commit()

        category_items = shop_service.get_items_by_category(category.id)
        assert len(category_items) == 2  # Only active

    def test_get_items_by_category_no_items(self, shop_service, in_memory_db):
        """Test getting items from category with no items."""
        category = ShopCategory(name="Empty Category", sort_order=1)
        in_memory_db.add(category)
        in_memory_db.commit()

        items = shop_service.get_items_by_category(category.id)
        assert len(items) == 0


class TestShopServiceItemMethods:
    """Test item management methods."""

    def test_get_all_items(self, shop_service, in_memory_db):
        """Test getting all items."""
        items = [
            ShopItem(name="Item 1", price=100, is_active=True),
            ShopItem(name="Item 2", price=200, is_active=True),
            ShopItem(name="Item 3", price=300, is_active=False),
        ]
        in_memory_db.add_all(items)
        in_memory_db.commit()

        all_items = shop_service.get_all_items()
        assert len(all_items) == 2  # Only active

    def test_get_item_by_id(self, shop_service, in_memory_db):
        """Test getting an item by ID."""
        item = ShopItem(name="Test Item", price=100, is_active=True)
        in_memory_db.add(item)
        in_memory_db.commit()

        retrieved = shop_service.get_item_by_id(item.id)
        assert retrieved is not None
        assert retrieved.name == "Test Item"

    def test_get_item_by_id_not_found(self, shop_service):
        """Test getting a non-existent item."""
        item = shop_service.get_item_by_id(999999)
        assert item is None


class TestShopServicePurchaseMethods:
    """Test purchase methods."""

    def test_purchase_item_success(self, shop_service, in_memory_db):
        """Test successful item purchase."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        item = ShopItem(name="Test Item", price=100, is_active=True)
        in_memory_db.add_all([user, item])
        in_memory_db.commit()

        purchase = shop_service.purchase_item(
            user_id=user.id,
            item_id=item.id
        )

        assert purchase is not None
        assert purchase.user_id == user.id
        assert purchase.item_id == item.id
        assert purchase.purchase_price == 100

        # Check user balance was updated
        in_memory_db.refresh(user)
        assert user.balance == 400
        assert user.total_purchases == 1

    def test_purchase_item_insufficient_balance(self, shop_service, in_memory_db):
        """Test purchasing with insufficient balance."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=50
        )
        item = ShopItem(name="Test Item", price=100, is_active=True)
        in_memory_db.add_all([user, item])
        in_memory_db.commit()

        with pytest.raises(ValueError, match="Insufficient balance"):
            shop_service.purchase_item(user_id=user.id, item_id=item.id)

    def test_purchase_item_not_found(self, shop_service, in_memory_db):
        """Test purchasing non-existent item."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        in_memory_db.add(user)
        in_memory_db.commit()

        with pytest.raises(ValueError, match="Item 999999 not found"):
            shop_service.purchase_item(user_id=user.id, item_id=999999)

    def test_purchase_item_inactive(self, shop_service, in_memory_db):
        """Test purchasing inactive item."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        item = ShopItem(name="Test Item", price=100, is_active=False)
        in_memory_db.add_all([user, item])
        in_memory_db.commit()

        with pytest.raises(ValueError, match="Item 1 is not active"):
            shop_service.purchase_item(user_id=user.id, item_id=item.id)

    def test_purchase_item_purchase_limit(self, shop_service, in_memory_db):
        """Test purchasing item with purchase limit."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        item = ShopItem(name="Test Item", price=100, is_active=True, purchase_limit=2)
        in_memory_db.add_all([user, item])
        in_memory_db.commit()

        # First purchase
        shop_service.purchase_item(user_id=user.id, item_id=item.id)
        # Second purchase
        shop_service.purchase_item(user_id=user.id, item_id=item.id)

        # Third purchase should fail
        with pytest.raises(ValueError, match="Purchase limit reached"):
            shop_service.purchase_item(user_id=user.id, item_id=item.id)

    def test_purchase_item_cooldown(self, shop_service, in_memory_db):
        """Test purchasing item with cooldown."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        item = ShopItem(name="Test Item", price=100, is_active=True, cooldown_hours=24)
        in_memory_db.add_all([user, item])
        in_memory_db.commit()

        # First purchase
        shop_service.purchase_item(user_id=user.id, item_id=item.id)

        # Second purchase should fail due to cooldown
        with pytest.raises(ValueError, match="Item 1 is on cooldown"):
            shop_service.purchase_item(user_id=user.id, item_id=item.id)


class TestShopServiceGetPurchases:
    """Test purchase history methods."""

    def test_get_user_purchases(self, shop_service, in_memory_db):
        """Test getting user's purchase history."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        item1 = ShopItem(name="Item 1", price=100, is_active=True)
        item2 = ShopItem(name="Item 2", price=200, is_active=True)
        in_memory_db.add_all([user, item1, item2])
        in_memory_db.commit()

        # Create purchases
        purchase1 = UserPurchase(
            user_id=user.id,
            item_id=item1.id,
            purchase_price=100,
            purchased_at=datetime.utcnow() - timedelta(hours=2),
            is_active=True
        )
        purchase2 = UserPurchase(
            user_id=user.id,
            item_id=item2.id,
            purchase_price=200,
            purchased_at=datetime.utcnow() - timedelta(hours=1),
            is_active=True
        )
        in_memory_db.add_all([purchase1, purchase2])
        in_memory_db.commit()

        purchases = shop_service.get_user_purchases(user.id)
        assert len(purchases) == 2
        assert purchases[0].item_id == item2.id  # Most recent first

    def test_get_user_purchases_empty(self, shop_service, in_memory_db):
        """Test getting purchases for user with no purchases."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        in_memory_db.add(user)
        in_memory_db.commit()

        purchases = shop_service.get_user_purchases(user.id)
        assert len(purchases) == 0

    def test_get_user_total_purchases(self, shop_service, in_memory_db):
        """Test getting total count of user's purchases."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        item = ShopItem(name="Item", price=100, is_active=True)
        in_memory_db.add_all([user, item])
        in_memory_db.commit()

        purchase1 = UserPurchase(user_id=user.id, item_id=item.id, purchase_price=100)
        purchase2 = UserPurchase(user_id=user.id, item_id=item.id, purchase_price=100)
        in_memory_db.add_all([purchase1, purchase2])
        in_memory_db.commit()

        total = shop_service.get_user_total_purchases(user.id)
        assert total == 2


class TestShopServiceItemActivation:
    """Test item activation methods."""

    def test_activate_item(self, shop_service, in_memory_db):
        """Test activating a purchased item."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        item = ShopItem(name="Test Item", price=100, is_active=True)
        in_memory_db.add_all([user, item])
        in_memory_db.commit()

        purchase = UserPurchase(
            user_id=user.id,
            item_id=item.id,
            purchase_price=100,
            is_active=False
        )
        in_memory_db.add(purchase)
        in_memory_db.commit()

        # First activation should work
        activated = shop_service.activate_item(user.id, item.id)
        assert activated is not None
        assert activated.is_active == True

        # Second activation should return the same item
        activated2 = shop_service.activate_item(user.id, item.id)
        assert activated2 is not None
        assert activated2.is_active == True

    def test_deactivate_item(self, shop_service, in_memory_db):
        """Test deactivating a purchased item."""
        user = User(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            balance=500
        )
        item = ShopItem(name="Test Item", price=100, is_active=True)
        in_memory_db.add_all([user, item])
        in_memory_db.commit()

        purchase = UserPurchase(
            user_id=user.id,
            item_id=item.id,
            purchase_price=100,
            is_active=True
        )
        in_memory_db.add(purchase)
        in_memory_db.commit()

        # First deactivation should work
        deactivated = shop_service.deactivate_item(user.id, item.id)
        assert deactivated is not None
        assert deactivated.is_active == False

        # Second deactivation should return the same item
        deactivated2 = shop_service.deactivate_item(user.id, item.id)
        assert deactivated2 is not None
        assert deactivated2.is_active == False
