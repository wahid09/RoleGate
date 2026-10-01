import pyotp
import pytest
from sqlalchemy import select

from app import models, security
from app.database import SessionLocal

EMAIL = "twofa@example.com"
PASSWORD = "Passw0rd123"


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now

    def advance(self, seconds=30):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(security, "_unix_time", c)
    return c


def code_for(secret, clock):
    return pyotp.TOTP(secret).at(int(clock.now))


def enroll(client, headers, clock):
    setup = client.post("/api/auth/2fa/setup", headers=headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    enabled = client.post("/api/auth/2fa/enable", headers=headers, json={"code": code_for(secret, clock)})
    assert enabled.status_code == 200, enabled.text
    return secret, enabled.json()["recovery_codes"]


def password_step(client):
    r = client.post("/api/auth/login", data={"username": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def test_enabling_2fa_makes_login_two_step(client, make_user, clock):
    headers = make_user(EMAIL)
    setup = client.post("/api/auth/2fa/setup", headers=headers).json()
    assert setup["qr_svg"].startswith("data:image/svg+xml")
    secret = setup["secret"]

    assert client.post("/api/auth/2fa/enable", headers=headers, json={"code": "000000"}).status_code == 400
    good = client.post("/api/auth/2fa/enable", headers=headers, json={"code": code_for(secret, clock)})
    assert good.status_code == 200
    assert len(good.json()["recovery_codes"]) == 8
    assert client.get("/api/auth/me", headers=headers).json()["totp_enabled"] is True

    first = password_step(client)
    assert first["mfa_required"] is True
    assert first["access_token"] is None
    mfa_token = first["mfa_token"]

    # the temporary token must never work as an access token
    as_bearer = client.get("/api/auth/me", headers={"Authorization": f"Bearer {mfa_token}"})
    assert as_bearer.status_code == 401

    wrong = client.post("/api/auth/login/2fa", json={"mfa_token": mfa_token, "code": "000000"})
    assert wrong.status_code == 400

    clock.advance(30)  # the enrolment code's time step is already used up
    ok = client.post("/api/auth/login/2fa", json={"mfa_token": mfa_token, "code": code_for(secret, clock)})
    assert ok.status_code == 200
    assert ok.json()["access_token"]
    assert client.cookies.get("refresh_token")

    # the same code cannot be used twice
    again = password_step(client)
    replay = client.post(
        "/api/auth/login/2fa", json={"mfa_token": again["mfa_token"], "code": code_for(secret, clock)}
    )
    assert replay.status_code == 400


def test_recovery_code_works_once(client, make_user, clock):
    headers = make_user(EMAIL)
    _, codes = enroll(client, headers, clock)

    first = password_step(client)
    ok = client.post("/api/auth/login/2fa", json={"mfa_token": first["mfa_token"], "code": codes[0]})
    assert ok.status_code == 200

    second = password_step(client)
    reuse = client.post("/api/auth/login/2fa", json={"mfa_token": second["mfa_token"], "code": codes[0]})
    assert reuse.status_code == 400
    other = client.post("/api/auth/login/2fa", json={"mfa_token": second["mfa_token"], "code": codes[1].upper()})
    assert other.status_code == 200


def test_disable_requires_password_and_code(client, make_user, clock):
    headers = make_user(EMAIL)
    _, codes = enroll(client, headers, clock)

    wrong_pw = client.post(
        "/api/auth/2fa/disable", headers=headers, json={"password": "not-it-1234", "code": codes[0]}
    )
    assert wrong_pw.status_code == 400

    ok = client.post("/api/auth/2fa/disable", headers=headers, json={"password": PASSWORD, "code": codes[0]})
    assert ok.status_code == 200
    assert client.get("/api/auth/me", headers=headers).json()["totp_enabled"] is False
    assert password_step(client)["access_token"]   # back to single-step sign-in


def test_admin_can_reset_two_factor(client, admin_headers, make_user, clock):
    headers = make_user(EMAIL)
    enroll(client, headers, clock)
    users = client.get("/api/users", headers=admin_headers).json()
    target = next(u for u in users if u["email"] == EMAIL)
    assert target["totp_enabled"] is True

    r = client.delete(f"/api/users/{target['id']}/2fa", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["totp_enabled"] is False
    assert password_step(client)["access_token"]
    assert client.delete(f"/api/users/{target['id']}/2fa", headers=admin_headers).status_code == 400


def test_wrong_code_is_audited(client, admin_headers, make_user, clock):
    headers = make_user(EMAIL)
    enroll(client, headers, clock)
    first = password_step(client)
    client.post("/api/auth/login/2fa", json={"mfa_token": first["mfa_token"], "code": "000000"})

    logs = client.get("/api/audit-logs", headers=admin_headers, params={"action": "auth.2fa_failed"}).json()
    assert logs["total"] == 1


def test_secret_is_encrypted_at_rest(client, make_user):
    headers = make_user(EMAIL)
    secret = client.post("/api/auth/2fa/setup", headers=headers).json()["secret"]
    with SessionLocal() as db:
        stored = db.scalar(select(models.User.totp_secret).where(models.User.email == EMAIL))
    assert stored and stored != secret and secret not in stored