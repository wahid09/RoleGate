import os
import re

# Must be set before the app imports its settings.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-only-for-automated-tests-0123456789")
os.environ.setdefault("FIRST_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("FIRST_ADMIN_PASSWORD", "Admin@12345")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import app
from app.seed import seed


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean_db(_schema):
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        seed(db)


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Capture outgoing emails instead of sending them."""
    sent: list[dict] = []
    monkeypatch.setattr(
        "app.routers.auth.send_email",
        lambda to, subject, body: sent.append({"to": to, "subject": subject, "body": body}),
    )
    return sent


@pytest.fixture
def token_from():
    def _extract(body: str) -> str:
        return re.search(r"token=([\w-]+)", body).group(1)

    return _extract


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers(client):
    r = client.post(
        "/api/auth/login",
        data={"username": settings.FIRST_ADMIN_EMAIL, "password": settings.FIRST_ADMIN_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def make_user(client, admin_headers):
    """Create a verified user with one role and return auth headers for them."""

    def _make(email: str, role: str = "user", password: str = "Passw0rd123") -> dict:
        roles = {r["name"]: r["id"] for r in client.get("/api/roles", headers=admin_headers).json()}
        created = client.post(
            "/api/users",
            headers=admin_headers,
            json={"full_name": "Test User", "email": email, "password": password, "role_ids": [roles[role]]},
        )
        assert created.status_code == 201, created.text
        login = client.post("/api/auth/login", data={"username": email, "password": password})
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    return _make