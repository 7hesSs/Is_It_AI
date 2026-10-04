"""
In-memory result cache - avoids re-running inference on identical content.

Keyed by SHA-256 of the input bytes. A plain OrderedDict used as a simple
LRU: oldest entry evicted once the cache hits MAX_ENTRIES. Process-local
and lost on restart - fine for a demo.
"""
import hashlib
from collections import OrderedDict
from typing import Optional

MAX_ENTRIES = 200

_cache: "OrderedDict[str, dict]" = OrderedDict()


def make_key(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def get(key: str) -> Optional[dict]:
    if key not in _cache:
        return None
    _cache.move_to_end(key)
    return _cache[key]


def set(key: str, value: dict) -> None:
    _cache[key] = value
    _cache.move_to_end(key)
    if len(_cache) > MAX_ENTRIES:
        _cache.popitem(last=False)
