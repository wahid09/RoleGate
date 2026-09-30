import pytest
import redis

from app import ratelimit
from app.config import settings

LOGIN = "/api/auth/login"


def _clear_keys():
    for pattern in ("rl:*", "lf:*"):
        for key in ratelimit._r.scan_iter(pattern):
            ratelimit._r.delete(key)


@pytest.fixture
def limiter(monkeypatch):
    """Enable rate limiting for one test. Skips when Redis isn't reachable."""
    try:
        ratelimit._r.ping()
    except redis.RedisError:
        pytest.skip("Redis is not reachable")
    _clear_keys()
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    yield
    _clear_keys()


def _login(client, email, password="wrong-password"):
    return client.post(LOGIN, data={"username": email, "password": password})


def test_login_is_rate_limited_per_ip(client, limiter):
    # different emails, so only the per-IP limit (10 per minute) can trigger
    for i in range(10):
        assert _login(client, f"user{i}@example.com").status_code == 401

    blocked = _login(client, "user99@example.com")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_account_locks_after_repeated_failures(client, limiter):
    email = settings.FIRST_ADMIN_EMAIL
    for _ in range(settings.LOGIN_MAX_FAILURES):
        assert _login(client, email).status_code == 401

    # even the correct password is refused while the account is locked
    locked = _login(client, email, settings.FIRST_ADMIN_PASSWORD)
    assert locked.status_code == 429


def test_successful_login_resets_failure_counter(client, limiter):
    email = settings.FIRST_ADMIN_EMAIL
    almost = settings.LOGIN_MAX_FAILURES - 1

    for _ in range(almost):
        assert _login(client, email).status_code == 401
    assert _login(client, email, settings.FIRST_ADMIN_PASSWORD).status_code == 200
    # would be 429 by now if the counter had not been cleared
    for _ in range(almost):
        assert _login(client, email).status_code == 401


def test_limiter_fails_open_when_redis_is_down(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    dead = redis.Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2, socket_timeout=0.2)
    monkeypatch.setattr(ratelimit, "_r", dead)

    r = _login(client, settings.FIRST_ADMIN_EMAIL, settings.FIRST_ADMIN_PASSWORD)
    assert r.status_code == 200