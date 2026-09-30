from app.config import settings


def test_admin_actions_are_audited(client, admin_headers):
    client.post(
        "/api/users", headers=admin_headers,
        json={"full_name": "Audited", "email": "audited@example.com", "password": "Passw0rd123"},
    )
    r = client.get("/api/audit-logs", headers=admin_headers, params={"action": "user."})
    assert r.status_code == 200
    entry = r.json()["items"][0]
    assert entry["action"] == "user.create"
    assert entry["actor_email"] == settings.FIRST_ADMIN_EMAIL
    assert entry["detail"]["email"] == "audited@example.com"


def test_failed_login_is_audited(client, admin_headers):
    client.post(
        "/api/auth/login",
        data={"username": settings.FIRST_ADMIN_EMAIL, "password": "wrong-password"},
    )
    r = client.get("/api/audit-logs", headers=admin_headers, params={"action": "auth.login_failed"})
    assert r.json()["total"] == 1


def test_audit_log_requires_permission(client, make_user):
    headers = make_user("mgr@example.com", "manager")
    assert client.get("/api/audit-logs", headers=headers).status_code == 403


def test_audit_log_pagination_and_actor_filter(client, admin_headers):
    for _ in range(3):
        client.post("/api/auth/login", data={"username": "nobody@example.com", "password": "wrong-password"})

    page = client.get("/api/audit-logs", headers=admin_headers, params={"page_size": 2}).json()
    assert len(page["items"]) == 2
    assert page["total"] >= 3

    by_actor = client.get("/api/audit-logs", headers=admin_headers, params={"actor": "nobody@"}).json()
    assert by_actor["total"] == 3