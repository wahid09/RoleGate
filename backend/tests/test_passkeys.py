import pytest
from sqlalchemy import select
from webauthn_helpers import SoftAuthenticator

from app import models
from app.database import SessionLocal

EMAIL = "pk@example.com"
PASSWORD = "Passw0rd123"


def add_passkey(client, headers, authenticator, name="Laptop", password=PASSWORD):
    opts = client.post("/api/auth/passkeys/register/options", headers=headers, json={"password": password})
    assert opts.status_code == 200, opts.text
    return client.post(
        "/api/auth/passkeys/register",
        headers=headers,
        json={"name": name, "credential": authenticator.create(opts.json())},
    )


def password_step(client):
    r = client.post("/api/auth/login", data={"username": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()


def passkey_login(client, mfa_token, authenticator, **kwargs):
    opts = client.post("/api/auth/login/webauthn/options", json={"mfa_token": mfa_token})
    assert opts.status_code == 200, opts.text
    return client.post(
        "/api/auth/login/webauthn",
        json={"mfa_token": mfa_token, "credential": authenticator.get(opts.json(), **kwargs)},
    )


@pytest.fixture
def key():
    return SoftAuthenticator()


def test_register_requires_password(client, make_user, key):
    headers = make_user(EMAIL)
    r = client.post("/api/auth/passkeys/register/options", headers=headers, json={"password": "wrong-pass-1"})
    assert r.status_code == 400


def test_adding_a_passkey_makes_login_two_step(client, make_user, key):
    headers = make_user(EMAIL)
    added = add_passkey(client, headers, key)
    assert added.status_code == 201, added.text
    assert added.json()["name"] == "Laptop"

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["passkey_count"] == 1 and me["mfa_enabled"] is True and me["totp_enabled"] is False

    first = password_step(client)
    assert first["mfa_required"] is True
    assert first["mfa_methods"] == ["passkey"]
    assert first["access_token"] is None

    # the temporary token is not a bearer token
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {first['mfa_token']}"}).status_code == 401

    ok = passkey_login(client, first["mfa_token"], key)
    assert ok.status_code == 200, ok.text
    assert ok.json()["access_token"]
    assert client.cookies.get("refresh_token")

    listed = client.get("/api/auth/passkeys", headers=headers).json()
    assert listed[0]["last_used_at"] is not None


def test_assertion_cannot_be_replayed(client, make_user, key):
    headers = make_user(EMAIL)
    add_passkey(client, headers, key)
    first = password_step(client)
    opts = client.post("/api/auth/login/webauthn/options", json={"mfa_token": first["mfa_token"]}).json()
    assertion = key.get(opts)
    body = {"mfa_token": first["mfa_token"], "credential": assertion}
    assert client.post("/api/auth/login/webauthn", json=body).status_code == 200
    # the challenge was consumed: the very same payload is refused
    assert client.post("/api/auth/login/webauthn", json=body).status_code == 400


def test_assertion_from_wrong_origin_is_rejected_and_audited(client, admin_headers, make_user, key):
    headers = make_user(EMAIL)
    add_passkey(client, headers, key)
    first = password_step(client)
    bad = passkey_login(client, first["mfa_token"], key, origin="https://evil.example")
    assert bad.status_code == 400
    logs = client.get("/api/audit-logs", headers=admin_headers, params={"action": "auth.2fa_failed"}).json()
    assert logs["total"] == 1


def test_unknown_authenticator_is_rejected(client, make_user, key):
    headers = make_user(EMAIL)
    add_passkey(client, headers, key)
    first = password_step(client)
    stranger = SoftAuthenticator()
    assert passkey_login(client, first["mfa_token"], stranger).status_code == 400


def test_same_credential_cannot_be_registered_twice(client, make_user, key):
    headers = make_user(EMAIL)
    assert add_passkey(client, headers, key).status_code == 201
    assert add_passkey(client, headers, key).status_code in (400, 409)


def test_removing_a_passkey_needs_the_password(client, make_user, key):
    headers = make_user(EMAIL)
    pk = add_passkey(client, headers, key).json()
    assert client.post(f"/api/auth/passkeys/{pk['id']}/remove", headers=headers, json={"password": "nope-12345"}).status_code == 400
    ok = client.post(f"/api/auth/passkeys/{pk['id']}/remove", headers=headers, json={"password": PASSWORD})
    assert ok.status_code == 200
    assert client.get("/api/auth/me", headers=headers).json()["mfa_enabled"] is False
    assert password_step(client)["access_token"]  # single-step sign-in again


def test_cannot_remove_someone_elses_passkey(client, make_user, key):
    a = make_user(EMAIL)
    b = make_user("other@example.com")
    pk = add_passkey(client, a, key).json()
    r = client.post(f"/api/auth/passkeys/{pk['id']}/remove", headers=b, json={"password": PASSWORD})
    assert r.status_code == 404


def test_admin_reset_removes_passkeys(client, admin_headers, make_user, key):
    headers = make_user(EMAIL)
    add_passkey(client, headers, key)
    target = next(u for u in client.get("/api/users", headers=admin_headers).json() if u["email"] == EMAIL)
    assert target["mfa_enabled"] is True and target["passkey_count"] == 1

    r = client.delete(f"/api/users/{target['id']}/2fa", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["mfa_enabled"] is False
    assert password_step(client)["access_token"]


def test_public_key_is_stored_not_a_secret(client, make_user, key):
    headers = make_user(EMAIL)
    add_passkey(client, headers, key)
    with SessionLocal() as db:
        row = db.scalar(select(models.WebAuthnCredential))
    assert row.sign_count == 0 and len(row.public_key) > 30
