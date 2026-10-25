from app.database import SessionLocal
from app.seed import seed


def create(client, headers, code="reports:export", description="Export reports"):
    return client.post("/api/permissions", headers=headers, json={"code": code, "description": description})


def test_permission_crud(client, admin_headers):
    made = create(client, admin_headers)
    assert made.status_code == 201
    body = made.json()
    assert body["builtin"] is False
    assert body["roles"] == ["admin"]          # admin receives every new permission

    listed = client.get("/api/permissions", headers=admin_headers).json()
    assert "reports:export" in [p["code"] for p in listed]

    updated = client.put(
        f"/api/permissions/{body['id']}", headers=admin_headers,
        json={"code": "reports:download", "description": "Download reports"},
    )
    assert updated.status_code == 200
    assert updated.json()["code"] == "reports:download"

    assert client.delete(f"/api/permissions/{body['id']}", headers=admin_headers).status_code == 204
    codes = [p["code"] for p in client.get("/api/permissions", headers=admin_headers).json()]
    assert "reports:download" not in codes


def test_validation_and_duplicates(client, admin_headers):
    assert create(client, admin_headers, code="NotValid").status_code == 422
    assert create(client, admin_headers, code="no-colon").status_code == 422
    assert create(client, admin_headers).status_code == 201
    assert create(client, admin_headers).status_code == 400


def test_builtin_permissions_are_protected(client, admin_headers):
    perms = {p["code"]: p for p in client.get("/api/permissions", headers=admin_headers).json()}
    users_read = perms["users:read"]
    assert users_read["builtin"] is True

    assert client.delete(f"/api/permissions/{users_read['id']}", headers=admin_headers).status_code == 400
    rename = client.put(
        f"/api/permissions/{users_read['id']}", headers=admin_headers,
        json={"code": "people:read", "description": "x"},
    )
    assert rename.status_code == 400

    ok = client.put(
        f"/api/permissions/{users_read['id']}", headers=admin_headers,
        json={"code": "users:read", "description": "List all users"},
    )
    assert ok.status_code == 200
    assert ok.json()["description"] == "List all users"


def test_admin_keeps_custom_permission_after_restart(client, admin_headers):
    create(client, admin_headers)
    with SessionLocal() as db:
        seed(db)                               # what happens on every app start
    me = client.get("/api/auth/me", headers=admin_headers).json()
    assert "reports:export" in me["permissions"]


def test_manager_cannot_manage_permissions(client, make_user):
    headers = make_user("mgr@example.com", "manager")
    assert client.get("/api/permissions", headers=headers).status_code == 403
    assert client.post("/api/permissions", headers=headers, json={"code": "a:b"}).status_code == 403


def test_permission_changes_are_audited(client, admin_headers):
    perm = create(client, admin_headers).json()
    client.delete(f"/api/permissions/{perm['id']}", headers=admin_headers)
    logs = client.get("/api/audit-logs", headers=admin_headers, params={"action": "permission."}).json()
    assert [i["action"] for i in logs["items"]] == ["permission.delete", "permission.create"]