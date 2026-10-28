import pytest
from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "Passw0rd123"
FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"


def sign_in(email, user_agent):
    """A second 'device': its own cookie jar and User-Agent."""
    c = TestClient(app)
    r = c.post(
        "/api/auth/login",
        data={"username": email, "password": PASSWORD},
        headers={"User-Agent": user_agent},
    )
    assert r.status_code == 200, r.text
    return c, {"Authorization": f"Bearer {r.json()['access_token']}"}


def sessions(client, headers):
    r = client.get("/api/auth/sessions", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def two_devices(client, make_user):
    headers = make_user("sess@example.com")          # `client` is device 1
    other, other_headers = sign_in("sess@example.com", FIREFOX)
    return client, headers, other, other_headers


def test_lists_each_device_once_and_marks_the_current_one(two_devices):
    a, ha, b, hb = two_devices
    seen_by_a = sessions(a, ha)
    assert len(seen_by_a) == 2
    assert [s["current"] for s in seen_by_a].count(True) == 1
    firefox = next(s for s in seen_by_a if "Firefox" in (s["user_agent"] or ""))
    assert firefox["current"] is False

    seen_by_b = sessions(b, hb)
    assert next(s for s in seen_by_b if s["current"])["id"] == firefox["id"]


def test_session_identity_survives_token_rotation(two_devices):
    a, ha, b, _hb = two_devices
    before = {s["id"] for s in sessions(a, ha)}
    assert b.post("/api/auth/refresh").status_code == 200
    assert a.post("/api/auth/refresh").status_code == 200
    after = sessions(a, ha)
    assert {s["id"] for s in after} == before and len(after) == 2


def test_revoking_one_device_does_not_sign_out_the_others(two_devices):
    a, ha, b, _hb = two_devices
    target = next(s for s in sessions(a, ha) if not s["current"])
    r = a.post(f"/api/auth/sessions/{target['id']}/revoke", headers=ha)
    assert r.status_code == 200, r.text

    # the revoked device cannot refresh... and that is not treated as token theft
    assert b.post("/api/auth/refresh").status_code == 401
    assert a.post("/api/auth/refresh").status_code == 200
    assert len(sessions(a, ha)) == 1


def test_cannot_revoke_the_current_device(two_devices):
    a, ha, _, _ = two_devices
    mine = next(s for s in sessions(a, ha) if s["current"])
    assert a.post(f"/api/auth/sessions/{mine['id']}/revoke", headers=ha).status_code == 400


def test_revoke_all_other_devices(two_devices):
    a, ha, b, _hb = two_devices
    third, _ = sign_in("sess@example.com", "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1")
    assert len(sessions(a, ha)) == 3
    r = a.post("/api/auth/sessions/revoke-others", headers=ha)
    assert r.json()["revoked"] == 2
    assert b.post("/api/auth/refresh").status_code == 401
    assert third.post("/api/auth/refresh").status_code == 401
    assert a.post("/api/auth/refresh").status_code == 200
    assert len(sessions(a, ha)) == 1


def test_cannot_touch_another_users_session(client, make_user, two_devices):
    a, ha, _, _ = two_devices
    victim = next(s for s in sessions(a, ha) if not s["current"])
    intruder = make_user("intruder@example.com")
    r = client.post(f"/api/auth/sessions/{victim['id']}/revoke", headers=intruder)
    assert r.status_code == 404


def test_signed_out_device_disappears(two_devices):
    a, ha, b, _hb = two_devices
    assert b.post("/api/auth/logout").status_code == 204
    assert len(sessions(a, ha)) == 1


def test_stolen_rotated_token_still_revokes_everything(client, make_user):
    make_user("theft@example.com")
    stolen = client.cookies.get("refresh_token")
    assert client.post("/api/auth/refresh").status_code == 200   # rotates; `stolen` is now spent
    thief = TestClient(app)
    thief.cookies.set("refresh_token", stolen, path="/api/auth")
    assert thief.post("/api/auth/refresh").status_code == 401
    assert client.post("/api/auth/refresh").status_code == 401   # the real user is signed out too
