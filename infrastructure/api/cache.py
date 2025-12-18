"""Cache abstraction for API responses.

Provides thread-safe caching with TTL support.
"""

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple


class Cache(ABC):
    """Abstract cache interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None = no expiration)
        """

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a specific cache entry.

        Args:
            key: Cache key to delete
        """


class InMemoryCache(Cache):
    """Thread-safe in-memory cache with TTL support."""

    def __init__(self, default_ttl: Optional[int] = 900) -> None:
        """Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 15 minutes)
        """
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key not in self._store:
                return None

            value, expiry = self._store[key]

            # Check if expired
            if expiry is not None and time.time() > expiry:
                del self._store[key]
                return None

            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        ttl_to_use = ttl if ttl is not None else self._default_ttl

        expiry: Optional[float] = None
        if ttl_to_use is not None:
            expiry = time.time() + ttl_to_use

        with self._lock:
            self._store[key] = (value, expiry)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._store.clear()

    def delete(self, key: str) -> None:
        """Delete a specific cache entry."""
        with self._lock:
            self._store.pop(key, None)

    def size(self) -> int:
        """Get number of items in cache."""
        with self._lock:
            return len(self._store)


class NullCache(Cache):
    """No-op cache that doesn't store anything.

    Useful for testing or when caching is disabled.
    """

    def get(self, key: str) -> Optional[Any]:
        """Always returns None."""
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Does nothing."""

    def clear(self) -> None:
        """Does nothing."""

    def delete(self, key: str) -> None:
        """Does nothing."""
