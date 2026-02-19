"""Property-based tests for BaseRepository using Hypothesis.

**Validates: Requirements 5.1, 5.2**

These tests verify that the BaseRepository maintains correctness properties
across a wide range of inputs and operations.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from src.repository.base import BaseRepository

# Create test base and model
Base = declarative_base()


class UserModel(Base):
    """Test model for repository testing."""
    __tablename__ = "test_users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(100), nullable=False)
    email = Column(String(100))
    is_active = Column(Boolean, default=True)
    balance = Column(Integer, default=0)


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create database session for testing."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def repository(session):
    """Create repository instance for testing."""
    return BaseRepository(UserModel, session)


# Hypothesis strategies for generating test data
username_strategy = st.text(
    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65),
    min_size=1,
    max_size=50
)

email_strategy = st.emails()

balance_strategy = st.integers(min_value=0, max_value=1000000)


class TestRepositoryCreateProperties:
    """Property-based tests for create operation."""
    
    @given(username=username_strategy, balance=balance_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_create_always_returns_instance_with_id(self, repository, username, balance):
        """
        Property: Created records always have a non-null ID.
        
        **Validates: Requirements 5.1**
        """
        user = repository.create(username=username, balance=balance)
        
        assert user is not None
        assert user.id is not None
        assert isinstance(user.id, int)
        assert user.id > 0
    
    @given(username=username_strategy, balance=balance_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_create_preserves_input_values(self, repository, username, balance):
        """
        Property: Created records preserve the input values.
        
        **Validates: Requirements 5.1**
        """
        user = repository.create(username=username, balance=balance)
        
        assert user.username == username
        assert user.balance == balance
    
    @given(username=username_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_created_record_is_retrievable(self, repository, username):
        """
        Property: Any created record can be retrieved by its ID.
        
        **Validates: Requirements 5.1**
        """
        created = repository.create(username=username)
        retrieved = repository.get(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.username == created.username


class TestRepositoryUpdateProperties:
    """Property-based tests for update operation."""
    
    @given(
        username=username_strategy,
        initial_balance=balance_strategy,
        new_balance=balance_strategy
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_update_changes_only_specified_fields(
        self, repository, username, initial_balance, new_balance
    ):
        """
        Property: Update only changes the specified fields, leaving others unchanged.
        
        **Validates: Requirements 5.1**
        """
        user = repository.create(username=username, balance=initial_balance)
        original_username = user.username
        
        updated = repository.update(user.id, balance=new_balance)
        
        assert updated.balance == new_balance
        assert updated.username == original_username
    
    @given(username=username_strategy, balance=balance_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_update_persists_across_queries(self, repository, username, balance):
        """
        Property: Updates are persisted and visible in subsequent queries.
        
        **Validates: Requirements 5.1**
        """
        user = repository.create(username=username, balance=0)
        repository.update(user.id, balance=balance)
        
        retrieved = repository.get(user.id)
        assert retrieved.balance == balance
    
    @given(non_existent_id=st.integers(min_value=1000, max_value=9999))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_update_nonexistent_returns_none(self, repository, non_existent_id):
        """
        Property: Updating a non-existent record returns None.
        
        **Validates: Requirements 5.1**
        """
        result = repository.update(non_existent_id, balance=100)
        assert result is None


class TestRepositoryDeleteProperties:
    """Property-based tests for delete operation."""
    
    @given(username=username_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_delete_removes_record(self, repository, username):
        """
        Property: Deleted records cannot be retrieved.
        
        **Validates: Requirements 5.1**
        """
        user = repository.create(username=username)
        user_id = user.id
        
        deleted = repository.delete(user_id)
        assert deleted is True
        
        retrieved = repository.get(user_id)
        assert retrieved is None
    
    @given(usernames=st.lists(username_strategy, min_size=2, max_size=10, unique=True))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_delete_affects_count(self, repository, usernames):
        """
        Property: Deleting records decreases the total count.
        
        **Validates: Requirements 5.1**
        """
        # Create multiple users
        for username in usernames:
            repository.create(username=username)
        
        initial_count = repository.count()
        assert initial_count == len(usernames)
        
        # Delete one user
        first_user = repository.get_by(username=usernames[0])
        repository.delete(first_user.id)
        
        final_count = repository.count()
        assert final_count == initial_count - 1
    
    @given(non_existent_id=st.integers(min_value=1000, max_value=9999))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_delete_nonexistent_returns_false(self, repository, non_existent_id):
        """
        Property: Deleting a non-existent record returns False.
        
        **Validates: Requirements 5.1**
        """
        result = repository.delete(non_existent_id)
        assert result is False


class TestRepositoryFilterProperties:
    """Property-based tests for filter operations."""
    
    @given(
        usernames=st.lists(username_strategy, min_size=3, max_size=10, unique=True),
        active_indices=st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=5, unique=True)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_filter_returns_only_matching_records(self, repository, usernames, active_indices):
        """
        Property: Filter returns only records matching the criteria.
        
        **Validates: Requirements 5.1**
        """
        assume(len(usernames) > max(active_indices, default=0))
        
        # Create users with different active states
        for i, username in enumerate(usernames):
            is_active = i in active_indices
            repository.create(username=username, is_active=is_active)
        
        # Filter for active users
        active_users = repository.filter(is_active=True)
        
        # All returned users should be active
        assert all(user.is_active for user in active_users)
        assert len(active_users) == len(active_indices)
    
    @given(usernames=st.lists(username_strategy, min_size=1, max_size=10, unique=True))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_filter_with_no_matches_returns_empty(self, repository, usernames):
        """
        Property: Filter with no matches returns empty list.
        
        **Validates: Requirements 5.1**
        """
        # Create users with is_active=True
        for username in usernames:
            repository.create(username=username, is_active=True)
        
        # Filter for inactive users
        inactive_users = repository.filter(is_active=False)
        assert inactive_users == []


class TestRepositoryCountProperties:
    """Property-based tests for count operation."""
    
    @given(usernames=st.lists(username_strategy, min_size=0, max_size=20, unique=True))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_count_matches_actual_records(self, repository, usernames):
        """
        Property: Count returns the actual number of records.
        
        **Validates: Requirements 5.1**
        """
        for username in usernames:
            repository.create(username=username)
        
        count = repository.count()
        assert count == len(usernames)
    
    @given(
        usernames=st.lists(username_strategy, min_size=3, max_size=10, unique=True),
        balance=balance_strategy
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_count_with_filter_matches_filtered_records(
        self, repository, usernames, balance
    ):
        """
        Property: Count with filter matches the number of filtered records.
        
        **Validates: Requirements 5.1**
        """
        # Create half with specific balance, half with 0
        for i, username in enumerate(usernames):
            user_balance = balance if i % 2 == 0 else 0
            repository.create(username=username, balance=user_balance)
        
        count_with_balance = repository.count(balance=balance)
        filtered_records = repository.filter(balance=balance)
        
        assert count_with_balance == len(filtered_records)


class TestRepositoryExistsProperties:
    """Property-based tests for exists operation."""
    
    @given(username=username_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exists_true_after_create(self, repository, username):
        """
        Property: exists returns True for created records.
        
        **Validates: Requirements 5.1**
        """
        repository.create(username=username)
        assert repository.exists(username=username) is True
    
    @given(username=username_strategy)
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exists_false_after_delete(self, repository, username):
        """
        Property: exists returns False for deleted records.
        
        **Validates: Requirements 5.1**
        """
        user = repository.create(username=username)
        repository.delete(user.id)
        
        assert repository.exists(username=username) is False
    
    @given(username=username_strategy)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exists_false_for_never_created(self, repository, username):
        """
        Property: exists returns False for records that were never created.
        
        **Validates: Requirements 5.1**
        """
        # Don't create anything
        assert repository.exists(username=username) is False


class TestRepositoryBulkCreateProperties:
    """Property-based tests for bulk_create operation."""
    
    @given(
        usernames=st.lists(username_strategy, min_size=1, max_size=20, unique=True)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_bulk_create_creates_all_records(self, repository, usernames):
        """
        Property: bulk_create creates all provided records.
        
        **Validates: Requirements 5.1**
        """
        items = [{"username": username} for username in usernames]
        created = repository.bulk_create(items)
        
        assert len(created) == len(usernames)
        assert repository.count() == len(usernames)
    
    @given(
        usernames=st.lists(username_strategy, min_size=1, max_size=10, unique=True),
        balance=balance_strategy
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_bulk_create_preserves_values(self, repository, usernames, balance):
        """
        Property: bulk_create preserves all input values.
        
        **Validates: Requirements 5.1**
        """
        items = [{"username": username, "balance": balance} for username in usernames]
        repository.bulk_create(items)
        
        all_users = repository.get_all()
        assert all(user.balance == balance for user in all_users)


class TestRepositoryGetAllPaginationProperties:
    """Property-based tests for get_all pagination."""
    
    @given(
        total=st.integers(min_value=5, max_value=20),
        limit=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pagination_limit_respected(self, repository, total, limit):
        """
        Property: get_all respects the limit parameter.
        
        **Validates: Requirements 5.1**
        """
        # Create records
        for i in range(total):
            repository.create(username=f"user_{i}")
        
        result = repository.get_all(limit=limit)
        assert len(result) == min(limit, total)
    
    @given(
        total=st.integers(min_value=10, max_value=20),
        offset=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pagination_offset_skips_records(self, repository, total, offset):
        """
        Property: get_all with offset skips the correct number of records.
        
        **Validates: Requirements 5.1**
        """
        assume(offset < total)
        
        # Create records
        for i in range(total):
            repository.create(username=f"user_{i}")
        
        result = repository.get_all(offset=offset)
        assert len(result) == total - offset

