from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "Passw0rd123"
EMAIL = "user@example.com"


def login(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/auth/login", data={"username": email, "password": password})


def register(client, email=EMAIL):
    return client.post(
        "/api/auth/register",
        json={"full_name": "Test User", "email": email, "password": PASSWORD},
    )


def make_verified(client, outbox, token_from, email=EMAIL):
    assert register(client, email).status_code == 201
    token = token_from(outbox[-1]["body"])
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200


def test_register_requires_email_verification(client, outbox, token_from):
    r = register(client)
    assert r.status_code == 201
    assert r.json()["email_verified"] is False
    assert outbox[-1]["to"] == EMAIL

    blocked = login(client)
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Email not verified"

    verify = client.post("/api/auth/verify-email", json={"token": token_from(outbox[-1]["body"])})
    assert verify.status_code == 200

    ok = login(client)
    assert ok.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {ok.json()['access_token']}"})
    assert me.json()["email_verified"] is True
    assert me.json()["permissions"] == ["dashboard:view"]


def test_duplicate_email_is_rejected(client):
    assert register(client).status_code == 201
    assert register(client).status_code == 400


def test_wrong_password_returns_401(client, outbox, token_from):
    make_verified(client, outbox, token_from)
    assert login(client, password="not-the-password").status_code == 401


def test_verify_with_bad_token_returns_400(client):
    assert client.post("/api/auth/verify-email", json={"token": "nope"}).status_code == 400


def test_refresh_rotates_and_detects_reuse(client, outbox, token_from):
    make_verified(client, outbox, token_from)
    assert login(client).status_code == 200
    old = client.cookies.get("refresh_token")
    assert old

    refreshed = client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    assert client.cookies.get("refresh_token") != old

    # replaying the already-rotated token is treated as theft...
    replay = TestClient(app).post("/api/auth/refresh", headers={"Cookie": f"refresh_token={old}"})
    assert replay.status_code == 401
    # ...and revokes the whole session family, including the newest token
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token(client, outbox, token_from):
    make_verified(client, outbox, token_from)
    login(client)
    old = client.cookies.get("refresh_token")

    assert client.post("/api/auth/logout").status_code == 204
    r = TestClient(app).post("/api/auth/refresh", headers={"Cookie": f"refresh_token={old}"})
    assert r.status_code == 401


def test_forgot_and_reset_password(client, outbox, token_from):
    make_verified(client, outbox, token_from)
    sent_before = len(outbox)

    # unknown email: same answer, no email
    unknown = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert unknown.status_code == 200
    assert len(outbox) == sent_before

    known = client.post("/api/auth/forgot-password", json={"email": EMAIL})
    assert known.status_code == 200
    assert outbox[-1]["subject"] == "Reset your password"

    token = token_from(outbox[-1]["body"])
    new_password = "N3wPassw0rd!"
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": new_password}).status_code == 200
    # the link is single-use
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Another1234"}).status_code == 400

    assert login(client).status_code == 401
    assert login(client, password=new_password).status_code == 200


def test_change_password(client, outbox, token_from):
    make_verified(client, outbox, token_from)
    headers = {"Authorization": f"Bearer {login(client).json()['access_token']}"}

    wrong = client.post(
        "/api/auth/change-password", headers=headers,
        json={"current_password": "wrong-one", "new_password": "N3wPassw0rd!"},
    )
    assert wrong.status_code == 400

    ok = client.post(
        "/api/auth/change-password", headers=headers,
        json={"current_password": PASSWORD, "new_password": "N3wPassw0rd!"},
    )
    assert ok.status_code == 200
    assert login(client).status_code == 401
    assert login(client, password="N3wPassw0rd!").status_code == 200