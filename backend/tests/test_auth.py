def test_register_and_login_json(client):
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "password": "password123", "full_name": "Alice"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@b.com"

    login_resp = client.post("/api/v1/auth/login-json", json={"email": "a@b.com", "password": "password123"})
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()


def test_duplicate_registration_rejected(client):
    payload = {"email": "dup@b.com", "password": "password123", "full_name": "Dup"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/v1/auth/register", json={"email": "c@b.com", "password": "password123", "full_name": "C"}
    )
    resp = client.post("/api/v1/auth/login-json", json={"email": "c@b.com", "password": "wrongpass"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_error"


def test_protected_route_requires_token(client):
    resp = client.get("/api/v1/voices")
    assert resp.status_code == 401
