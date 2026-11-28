from fastapi.testclient import TestClient


def test_register_user_success(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "New User",
            "email": "newuser@example.com",
            "password": "password123",
            "role": "customer",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["name"] == "New User"
    assert "id" in data
    assert "password_hash" not in data  # Security check: password_hash never exposed!


def test_register_duplicate_email_fails(client: TestClient):
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "User One",
            "email": "duplicate@example.com",
            "password": "password123",
            "role": "customer",
        },
    )
    # Attempt duplicate
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "User Two",
            "email": "duplicate@example.com",
            "password": "password456",
            "role": "customer",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_login_success(client: TestClient):
    # Register
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Login User",
            "email": "loginuser@example.com",
            "password": "correctpassword",
            "role": "customer",
        },
    )
    # Login
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "loginuser@example.com", "password": "correctpassword"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password_fails(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={
            "name": "Login User",
            "email": "loginuser2@example.com",
            "password": "correctpassword",
            "role": "customer",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "loginuser2@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_get_current_user_profile(client: TestClient, customer_headers: dict):
    response = client.get("/api/v1/users/me", headers=customer_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "customer@cartify.com"
    assert data["role"] == "customer"


def test_get_current_user_unauthorized(client: TestClient):
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
