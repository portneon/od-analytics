def test_register_then_login(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "Acme Inc", "name": "Alice", "email": "alice@acme.com", "password": "password123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["access_token"]

    resp = client.post("/api/v1/auth/login", json={"email": "alice@acme.com", "password": "password123"})
    assert resp.status_code == 200
    assert resp.json()["data"]["user"]["email"] == "alice@acme.com"


def test_login_wrong_password_returns_401(client):
    client.post(
        "/api/v1/auth/register",
        json={"tenant_name": "Acme Inc", "name": "Alice", "email": "alice2@acme.com", "password": "password123"},
    )
    resp = client.post("/api/v1/auth/login", json={"email": "alice2@acme.com", "password": "wrong-password"})
    assert resp.status_code == 401
    assert resp.json()["success"] is False
    assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_duplicate_registration_conflicts(client):
    payload = {"tenant_name": "Acme Inc", "name": "Alice", "email": "dup@acme.com", "password": "password123"}
    client.post("/api/v1/auth/register", json=payload)
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


def test_protected_route_requires_auth(client):
    resp = client.get("/api/v1/datasets")
    assert resp.status_code == 401
