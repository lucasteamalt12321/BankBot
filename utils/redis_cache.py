"""Redis cache backend for production use."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis-based cache with TTL support.

    Falls back to no-op operations if Redis is unavailable.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        key_prefix: str = "bankbot:",
        default_ttl: int = 300,
    ) -> None:
        """Initialize Redis connection.

        Args:
            host: Redis host.
            port: Redis port.
            db: Redis database number.
            password: Redis password (optional).
            key_prefix: Prefix for all keys.
            default_ttl: Default TTL in seconds.
        """
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self._client: Optional[redis.Redis] = None
        self._connect(host, port, db, password)

    def _connect(
        self,
        host: str,
        port: int,
        db: int,
        password: Optional[str],
    ) -> None:
        """Establish Redis connection."""
        try:
            self._client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            self._client.ping()
            logger.info("Redis connected: %s:%d", host, port)
        except redis.ConnectionError:
            logger.warning("Redis unavailable, cache disabled")
            self._client = None

    def _key(self, key: str) -> str:
        """Apply prefix to key."""
        return f"{self.key_prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis.

        Args:
            key: Cache key (prefix will be added).

        Returns:
            Cached value or None if not found/expired.
        """
        if self._client is None:
            return None
        try:
            full_key = self._key(key)
            value = self._client.get(full_key)
            if value is not None:
                return json.loads(value)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.warning("Redis get failed: %s", e)
            return None

    def set(self, key: str, value: Any, ttl: int = 0) -> None:
        """Set value in Redis.

        Args:
            key: Cache key (prefix will be added).
            value: Value to cache (must be JSON-serializable).
            ttl: Time-to-live in seconds (0 = use default).
        """
        if self._client is None:
            return
        try:
            full_key = self._key(key)
            serialized = json.dumps(value)
            effective_ttl = ttl if ttl > 0 else self.default_ttl
            if effective_ttl > 0:
                self._client.setex(full_key, effective_ttl, serialized)
            else:
                self._client.set(full_key, serialized)
        except (redis.RedisError, TypeError) as e:
            logger.warning("Redis set failed: %s", e)

    def delete(self, key: str) -> None:
        """Delete key from Redis.

        Args:
            key: Cache key (prefix will be added).
        """
        if self._client is None:
            return
        try:
            self._client.delete(self._key(key))
        except redis.RedisError as e:
            logger.warning("Redis delete failed: %s", e)

    def clear(self) -> None:
        """Clear all keys with prefix."""
        if self._client is None:
            return
        try:
            pattern = f"{self.key_prefix}*"
            cursor = 0
            while True:
                cursor, keys = self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    self._client.delete(*keys)
                if cursor == 0:
                    break
        except redis.RedisError as e:
            logger.warning("Redis clear failed: %s", e)

    def health_check(self) -> bool:
        """Check Redis connection health.

        Returns:
            True if Redis is available, False otherwise.
        """
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except redis.RedisError:
            return False


_redis_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """Get or create Redis cache instance."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache


def init_redis_cache(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    password: Optional[str] = None,
) -> RedisCache:
    """Initialize Redis cache with custom settings.

    Args:
        host: Redis host.
        port: Redis port.
        db: Redis database number.
        password: Redis password (optional).

    Returns:
        Configured RedisCache instance.
    """
    global _redis_cache
    _redis_cache = RedisCache(host, port, db, password)
    return _redis_cache
