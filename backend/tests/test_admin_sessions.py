import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

EMAIL = "victim@example.com"
PASSWORD = "Passw0rd123"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"


def sign_in(user_agent=None):
    c = TestClient(app)
    r = c.post(
        "/api/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"User-Agent": user_agent} if user_agent else {},
    )
    assert r.status_code == 200, r.text
    return c, {"Authorization": f"Bearer {r.json()['access_token']}"}


def user_id(client, admin_headers):
    users = client.get("/api/users", headers=admin_headers).json()
    return next(u["id"] for u in users if u["email"] == EMAIL)


@pytest.fixture
def victim(client, admin_headers, make_user):
    make_user(EMAIL)                        # `client` is also signed in as the victim: device 1
    other, other_headers = sign_in(FIREFOX)  # device 2
    return other, other_headers, user_id(client, admin_headers)


def test_admin_sees_the_users_devices(client, admin_headers, victim):
    _, _, uid = victim
    r = client.get(f"/api/users/{uid}/sessions", headers=admin_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2
    assert any("Firefox" in (s["user_agent"] or "") for s in r.json())


def test_sign_out_everywhere_is_immediate(client, admin_headers, victim):
    other, other_headers, uid = victim
    assert client.get("/api/auth/me", headers=other_headers).status_code == 200

    r = client.post(f"/api/users/{uid}/sessions/revoke-all", headers=admin_headers)
    assert r.status_code == 200 and r.json()["revoked"] == 2

    # the already-issued access token stops working right away, not after 15 minutes
    assert client.get("/api/auth/me", headers=other_headers).status_code == 401
    assert other.post("/api/auth/refresh").status_code == 401

    # the user can sign in again afterwards (wait out the one-second token timestamp granularity)
    time.sleep(1.1)
    _, fresh = sign_in()
    assert client.get("/api/auth/me", headers=fresh).status_code == 200


def test_signing_out_one_device(client, admin_headers, victim):
    other, _, uid = victim
    target = next(
        s for s in client.get(f"/api/users/{uid}/sessions", headers=admin_headers).json()
        if "Firefox" in (s["user_agent"] or "")
    )
    r = client.post(f"/api/users/{uid}/sessions/{target['id']}/revoke", headers=admin_headers)
    assert r.status_code == 200
    assert other.post("/api/auth/refresh").status_code == 401
    assert len(client.get(f"/api/users/{uid}/sessions", headers=admin_headers).json()) == 1
    assert client.post(f"/api/users/{uid}/sessions/nope/revoke", headers=admin_headers).status_code == 404


def test_admin_cannot_use_this_on_themselves(client, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert client.post(f"/api/users/{me['id']}/sessions/revoke-all", headers=admin_headers).status_code == 400
    assert client.get(f"/api/users/{me['id']}/sessions", headers=admin_headers).status_code == 400


def test_requires_users_update_permission(client, make_user, victim):
    _, _, uid = victim
    plain = make_user("plain@example.com")
    assert client.get(f"/api/users/{uid}/sessions", headers=plain).status_code == 403
    assert client.post(f"/api/users/{uid}/sessions/revoke-all", headers=plain).status_code == 403


def test_unknown_user_is_404(client, admin_headers):
    assert client.post("/api/users/99999/sessions/revoke-all", headers=admin_headers).status_code == 404


def test_action_is_audited(client, admin_headers, victim):
    _, _, uid = victim
    client.post(f"/api/users/{uid}/sessions/revoke-all", headers=admin_headers)
    logs = client.get("/api/audit-logs", headers=admin_headers, params={"action": "user.sessions"}).json()
    assert logs["total"] == 1
    assert logs["items"][0]["detail"]["sessions"] == 2
