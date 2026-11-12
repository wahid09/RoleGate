import pytest


@pytest.fixture
def people(client, admin_headers, make_user):
    for name in ("alice", "bob", "carol", "dave", "erin"):
        make_user(f"{name}@example.com")
    return admin_headers


def search(client, headers, **params):
    r = client.get("/api/users/search", headers=headers, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def emails(page):
    return [u["email"] for u in page["items"]]


def test_pagination(client, people):
    first = search(client, people, page=1, page_size=2)
    assert first["total"] == 6 and first["page"] == 1 and first["page_size"] == 2
    assert len(first["items"]) == 2

    seen = []
    for p in (1, 2, 3):
        seen += emails(search(client, people, page=p, page_size=2))
    assert len(seen) == 6 and len(set(seen)) == 6          # no overlaps, nothing missing
    assert search(client, people, page=4, page_size=2)["items"] == []   # past the end is empty, not an error


def test_search_matches_email_and_is_case_insensitive(client, people):
    assert emails(search(client, people, search="ALI")) == ["alice@example.com"]
    assert search(client, people, search="example.com")["total"] == 6
    assert search(client, people, search="nobody-like-this")["total"] == 0


def test_search_treats_wildcards_literally(client, people):
    assert search(client, people, search="%")["total"] == 0
    assert search(client, people, search="_")["total"] == 0


def test_status_filter(client, people):
    users = client.get("/api/users", headers=people).json()
    bob = next(u for u in users if u["email"] == "bob@example.com")
    assert client.patch(f"/api/users/{bob['id']}/active", headers=people, json={"is_active": False}).status_code == 200

    assert emails(search(client, people, status="disabled")) == ["bob@example.com"]
    active = search(client, people, status="active")
    assert active["total"] == 5 and "bob@example.com" not in emails(active)


def test_role_filter(client, people):
    roles = client.get("/api/roles", headers=people).json()
    admin_role = next(r for r in roles if r["name"] == "admin")
    page = search(client, people, role_id=admin_role["id"])
    assert emails(page) == ["admin@example.com"]


def test_sorting(client, people):
    asc = emails(search(client, people, sort="email", order="asc"))
    desc = emails(search(client, people, sort="email", order="desc"))
    assert asc == sorted(asc) and desc == asc[::-1]


def test_filters_combine_and_total_ignores_page_size(client, people):
    users = client.get("/api/users", headers=people).json()
    bob = next(u for u in users if u["email"] == "bob@example.com")
    client.patch(f"/api/users/{bob['id']}/active", headers=people, json={"is_active": False})

    assert emails(search(client, people, search="bo", status="disabled")) == ["bob@example.com"]
    assert search(client, people, search="bo", status="active")["total"] == 0      # filters are ANDed

    page = search(client, people, search="example.com", page=1, page_size=2)
    assert page["total"] == 6 and len(page["items"]) == 2                        # total is not the page length


def test_validation_and_permissions(client, people, make_user):
    assert client.get("/api/users/search", headers=people, params={"page_size": 1000}).status_code == 422
    assert client.get("/api/users/search", headers=people, params={"sort": "password"}).status_code == 422
    assert client.get("/api/users/search", headers=people, params={"status": "weird"}).status_code == 422
    assert client.get("/api/users/search").status_code == 401
    plain = make_user("plain@example.com")                    # default role has no users:read
    assert client.get("/api/users/search", headers=plain).status_code == 403


def test_existing_list_endpoint_is_unchanged(client, people):
    r = client.get("/api/users", headers=people)
    assert isinstance(r.json(), list) and len(r.json()) == 6
