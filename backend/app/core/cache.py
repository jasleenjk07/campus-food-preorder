import json
import logging

import redis

from app.config import settings

logger = logging.getLogger(__name__)

redis_client = None
try:
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=False,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
except Exception as exc:
    logger.warning("Redis cache client init failed: %s", exc)
    redis_client = None

CACHE_TTL = 300  # 5 minutes


def get_cache(key: str):
    if redis_client is None:
        return None
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as exc:
        logger.warning("Cache get failed for %s: %s", key, exc)
    return None


def set_cache(key: str, value):
    if redis_client is None:
        return
    try:
        redis_client.setex(key, CACHE_TTL, json.dumps(value))
    except Exception as exc:
        logger.warning("Cache set failed for %s: %s", key, exc)


def delete_cache(key: str):
    if redis_client is None:
        return
    try:
        redis_client.delete(key)
    except Exception as exc:
        logger.warning("Cache delete failed for %s: %s", key, exc)
