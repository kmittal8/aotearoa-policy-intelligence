"""
Simple in-memory TTL cache for Stats NZ API responses.

Stats NZ census data doesn't change between releases, so caching is safe.
Default TTLs:
  - dataflow list:  24 hours  (rarely changes)
  - datastructures: 6 hours
  - observations:   1 hour    (business data may update more often)
"""
import time
import hashlib
import json
from typing import Any, Optional

_cache: dict[str, tuple[float, Any]] = {}  # key → (expires_at, value)


def _make_key(namespace: str, **kwargs) -> str:
    payload = json.dumps(kwargs, sort_keys=True)
    digest = hashlib.md5(payload.encode()).hexdigest()[:12]
    return f"{namespace}:{digest}"


def get(namespace: str, **kwargs) -> Optional[Any]:
    key = _make_key(namespace, **kwargs)
    entry = _cache.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if time.monotonic() > expires_at:
        del _cache[key]
        return None
    return value


def set(namespace: str, value: Any, ttl_seconds: int, **kwargs) -> None:
    key = _make_key(namespace, **kwargs)
    _cache[key] = (time.monotonic() + ttl_seconds, value)


def invalidate(namespace: str) -> int:
    """Remove all entries for a namespace. Returns count removed."""
    keys = [k for k in _cache if k.startswith(f"{namespace}:")]
    for k in keys:
        del _cache[k]
    return len(keys)


def stats() -> dict:
    now = time.monotonic()
    live = sum(1 for _, (exp, _) in _cache.items() if exp > now)
    return {"total_entries": len(_cache), "live_entries": live}


# TTL constants
TTL_DATAFLOWS = 24 * 3600   # 24 h
TTL_DATASTRUCTURE = 6 * 3600  # 6 h
TTL_OBSERVATIONS = 3600       # 1 h
