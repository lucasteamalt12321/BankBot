"""
Cache module with in-memory backend.
Can be swapped for Redis in production.
"""

import time
from typing import Optional, Any, Dict
from threading import Lock


class Cache:
    """Simple in-memory cache with TTL support."""

    def __init__(self):
        self._store: Dict[str, tuple[Any, float]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key in self._store:
                value, expires_at = self._store[key]
                if expires_at == 0 or expires_at > time.time():
                    return value
                del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL (seconds)."""
        with self._lock:
            expires_at = time.time() + ttl if ttl > 0 else 0
            self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cache."""
        with self._lock:
            self._store.clear()

    def cleanup(self) -> int:
        """Remove expired keys. Returns count of removed keys."""
        count = 0
        with self._lock:
            now = time.time()
            expired = [
                k for k, (_, exp) in self._store.items() if exp > 0 and exp <= now
            ]
            for key in expired:
                del self._store[key]
                count += 1
        return count


cache = Cache()


def get_balance_cached(user_id: int) -> Optional[int]:
    """Get cached balance for user."""
    return cache.get(f"balance:{user_id}")


def set_balance_cached(user_id: int, balance: int, ttl: int = 60) -> None:
    """Cache user balance."""
    cache.set(f"balance:{user_id}", balance, ttl)


def invalidate_balance(user_id: int) -> None:
    """Invalidate cached balance."""
    cache.delete(f"balance:{user_id}")


def get_user_cached(user_id: int) -> Optional[dict]:
    """Get cached user profile."""
    return cache.get(f"user:{user_id}")


def set_user_cached(user_id: int, profile: dict, ttl: int = 300) -> None:
    """Cache user profile."""
    cache.set(f"user:{user_id}", profile, ttl)
