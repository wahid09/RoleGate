from app.config import settings

PASSWORD = "Passw0rd123"


def test_requests_without_token_are_rejected(client):
    assert client.get("/api/users").status_code == 401


def test_regular_user_is_forbidden(client, make_user):
    headers = make_user("plain@example.com", "user")
    r = client.get("/api/users", headers=headers)
    assert r.status_code == 403
    assert "users:read" in r.json()["detail"]


def test_admin_can_list_users(client, admin_headers):
    r = client.get("/api/users", headers=admin_headers)
    assert r.status_code == 200
    assert [u["email"] for u in r.json()] == [settings.FIRST_ADMIN_EMAIL]


def test_manager_can_read_but_not_create_users(client, make_user):
    headers = make_user("boss@example.com", "manager")
    assert client.get("/api/users", headers=headers).status_code == 200
    r = client.post(
        "/api/users", headers=headers,
        json={"full_name": "X Y", "email": "x@example.com", "password": PASSWORD},
    )
    assert r.status_code == 403


def test_admin_creates_user_who_can_sign_in_immediately(client, admin_headers):
    r = client.post(
        "/api/users", headers=admin_headers,
        json={"full_name": "New Person", "email": "New@Example.com", "password": PASSWORD},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "new@example.com"                 # normalised
    assert body["email_verified"] is True                     # admin-created accounts skip verification
    assert [role["name"] for role in body["roles"]] == ["user"]   # default role
    login = client.post("/api/auth/login", data={"username": "new@example.com", "password": PASSWORD})
    assert login.status_code == 200


def test_assigning_roles_changes_permissions(client, admin_headers, make_user):
    make_user("promote@example.com", "user")
    users = client.get("/api/users", headers=admin_headers).json()
    target = next(u for u in users if u["email"] == "promote@example.com")
    roles = {r["name"]: r["id"] for r in client.get("/api/roles", headers=admin_headers).json()}

    r = client.put(f"/api/users/{target['id']}/roles", headers=admin_headers, json={"role_ids": [roles["manager"]]})
    assert r.status_code == 200
    assert "users:read" in r.json()["permissions"]


def test_role_lifecycle_and_protected_roles(client, admin_headers):
    perms = client.get("/api/roles/permissions", headers=admin_headers).json()
    read_users = next(p["id"] for p in perms if p["code"] == "users:read")

    created = client.post(
        "/api/roles", headers=admin_headers,
        json={"name": "auditor", "description": "Read only", "permission_ids": [read_users]},
    )
    assert created.status_code == 201
    role_id = created.json()["id"]

    updated = client.put(
        f"/api/roles/{role_id}", headers=admin_headers,
        json={"name": "auditor", "description": "Updated", "permission_ids": []},
    )
    assert updated.status_code == 200
    assert updated.json()["permissions"] == []

    assert client.delete(f"/api/roles/{role_id}", headers=admin_headers).status_code == 204

    roles = {r["name"]: r["id"] for r in client.get("/api/roles", headers=admin_headers).json()}
    assert client.delete(f"/api/roles/{roles['admin']}", headers=admin_headers).status_code == 400
    r = client.put(f"/api/roles/{roles['admin']}", headers=admin_headers, json={"name": "admin", "permission_ids": []})
    assert r.status_code == 400


def test_disabled_user_cannot_sign_in_and_admin_cannot_disable_self(client, admin_headers, make_user):
    make_user("gone@example.com", "user")
    users = client.get("/api/users", headers=admin_headers).json()
    target = next(u for u in users if u["email"] == "gone@example.com")

    r = client.patch(f"/api/users/{target['id']}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 200
    login = client.post("/api/auth/login", data={"username": "gone@example.com", "password": PASSWORD})
    assert login.status_code == 403

    me = next(u for u in users if u["email"] == settings.FIRST_ADMIN_EMAIL)
    r = client.patch(f"/api/users/{me['id']}/active", headers=admin_headers, json={"is_active": False})
    assert r.status_code == 400