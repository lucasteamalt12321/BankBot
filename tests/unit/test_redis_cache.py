"""Unit tests for utils.redis_cache module."""

from unittest.mock import MagicMock, patch

import pytest

from utils.redis_cache import RedisCache, get_redis_cache, init_redis_cache


class TestRedisCache:
    """Tests for RedisCache class."""

    def test_init_default_values(self):
        """Test initialization with defaults."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = RedisCache()

            assert cache.key_prefix == "bankbot:"
            assert cache.default_ttl == 300
            assert cache._client is not None
            mock_redis.assert_called_once()

    def test_init_custom_values(self):
        """Test initialization with custom settings."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = RedisCache(
                host="redis.example.com",
                port=6380,
                db=1,
                key_prefix="test:",
                default_ttl=60,
            )

            assert cache.key_prefix == "test:"
            assert cache.default_ttl == 60
            mock_redis.assert_called_once_with(
                host="redis.example.com",
                port=6380,
                db=1,
                password=None,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )

    def test_init_connection_failure(self):
        """Test graceful handling of connection failure."""
        import redis

        with patch("redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.ConnectionError()

            cache = RedisCache()

            assert cache._client is None

    def test_key_prefix(self):
        """Test key prefix is applied."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = RedisCache(key_prefix="custom:")

            assert cache._key("balance:123") == "custom:balance:123"

    def test_get_success(self):
        """Test successful get from Redis."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True
            mock_instance.get.return_value = '{"balance": 100}'

            cache = RedisCache()
            result = cache.get("user:123")

            assert result == {"balance": 100}
            mock_instance.get.assert_called_once_with("bankbot:user:123")

    def test_get_not_found(self):
        """Test get returns None when key not found."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True
            mock_instance.get.return_value = None

            cache = RedisCache()
            result = cache.get("user:999")

            assert result is None

    def test_get_no_client(self):
        """Test get returns None when Redis unavailable."""
        import redis

        with patch("redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.ConnectionError()

            cache = RedisCache()
            result = cache.get("user:123")

            assert result is None

    def test_set_success(self):
        """Test successful set to Redis."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = RedisCache()
            cache.set("user:123", {"balance": 500}, ttl=120)

            mock_instance.setex.assert_called_once()
            call_args = mock_instance.setex.call_args
            assert call_args[0][0] == "bankbot:user:123"
            assert call_args[0][1] == 120

    def test_set_default_ttl(self):
        """Test set uses default TTL when not specified."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = RedisCache(default_ttl=300)
            cache.set("user:123", {"balance": 500})

            call_args = mock_instance.setex.call_args
            assert call_args[0][1] == 300

    def test_set_eternal(self):
        """Test set with TTL=0 stores without expiry using default_ttl."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = RedisCache(default_ttl=0)
            cache.set("user:123", {"balance": 500}, ttl=0)

            mock_instance.set.assert_called_once()
            mock_instance.setex.assert_not_called()

    def test_set_no_client(self):
        """Test set does nothing when Redis unavailable."""
        import redis

        with patch("redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.ConnectionError()

            cache = RedisCache()
            cache.set("user:123", {"balance": 500})

    def test_delete_success(self):
        """Test successful delete from Redis."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = RedisCache()
            cache.delete("user:123")

            mock_instance.delete.assert_called_once_with("bankbot:user:123")

    def test_delete_no_client(self):
        """Test delete does nothing when Redis unavailable."""
        import redis

        with patch("redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.ConnectionError()

            cache = RedisCache()
            cache.delete("user:123")

    def test_clear_success(self):
        """Test clear deletes all keys with prefix."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True
            mock_instance.scan.side_effect = [
                (0, ["bankbot:user:1", "bankbot:balance:1"]),
                (0, []),
            ]

            cache = RedisCache()
            cache.clear()

            mock_instance.delete.assert_called_once()

    def test_clear_no_client(self):
        """Test clear does nothing when Redis unavailable."""
        import redis

        with patch("redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.ConnectionError()

            cache = RedisCache()
            cache.clear()

    def test_health_check_success(self):
        """Test health check returns True when Redis available."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = RedisCache()
            assert cache.health_check() is True

    def test_health_check_failure(self):
        """Test health check returns False when Redis unavailable."""
        import redis

        with patch("redis.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = redis.ConnectionError()

            cache = RedisCache()
            assert cache.health_check() is False


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_init_redis_cache(self):
        """Test init_redis_cache creates singleton."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            cache = init_redis_cache(host="custom.host", port=6380)

            assert cache._client is not None
            assert cache.key_prefix == "bankbot:"

    def test_get_redis_cache_after_init(self):
        """Test get_redis_cache returns initialized instance."""
        with patch("redis.Redis") as mock_redis:
            mock_instance = MagicMock()
            mock_redis.return_value = mock_instance
            mock_instance.ping.return_value = True

            init_redis_cache()
            cache = get_redis_cache()

            assert cache is not None
