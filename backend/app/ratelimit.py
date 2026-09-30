import logging

import redis
from fastapi import HTTPException, Request

from .config import settings

log = logging.getLogger(__name__)
_r = redis.Redis.from_url(
    settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1
)


def client_ip(request: Request) -> str:
    # Nginx overwrites X-Real-IP with the real client address
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def _hit(key: str, window: int) -> tuple[int, int]:
    pipe = _r.pipeline()
    pipe.incr(key)
    pipe.ttl(key)
    count, ttl = pipe.execute()
    if ttl < 0:                      # first hit (or a key that lost its expiry)
        _r.expire(key, window)
        ttl = window
    return count, ttl


def rate_limit(name: str, limit: int, window: int):
    """FastAPI dependency: at most `limit` calls per `window` seconds per client IP."""

    def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED:
            return
        try:
            count, ttl = _hit(f"rl:{name}:{client_ip(request)}", window)
        except redis.RedisError:
            log.warning("Redis unavailable, rate limiting skipped")   # fail open
            return
        if count > limit:
            raise HTTPException(
                429,
                "Too many requests. Please try again later.",
                headers={"Retry-After": str(ttl)},
            )

    return dependency


# --- per-account lockout after repeated failed logins -----------------------

def login_locked(email: str) -> bool:
    if not settings.RATE_LIMIT_ENABLED:
        return False
    try:
        value = _r.get(f"lf:{email}")
        return value is not None and int(value) >= settings.LOGIN_MAX_FAILURES
    except redis.RedisError:
        return False


def login_failed(email: str) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    try:
        _hit(f"lf:{email}", settings.LOGIN_LOCK_SECONDS)
    except redis.RedisError:
        pass


def login_ok(email: str) -> None:
    try:
        _r.delete(f"lf:{email}")
    except redis.RedisError:
        pass