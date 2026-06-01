"""Redis 缓存辅助工具。"""
import json
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

settings = get_settings()

_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _pool


async def cache_get(key: str) -> Any | None:
    r = get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    r = get_redis()
    await r.set(key, json.dumps(value, default=str), ex=ttl)


async def cache_delete(key: str) -> None:
    r = get_redis()
    await r.delete(key)
