from fastapi.testclient import TestClient


def test_list_categories_public(client: TestClient, test_category):
    response = client.get("/api/v1/categories/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["slug"] == "electronics"


def test_get_category_by_slug(client: TestClient, test_category):
    response = client.get("/api/v1/categories/slug/electronics")
    assert response.status_code == 200
    assert response.json()["name"] == "Electronics"


def test_get_category_not_found(client: TestClient):
    response = client.get("/api/v1/categories/999")
    assert response.status_code == 404


def test_create_category_shop_owner_permitted(client: TestClient, shop_owner_headers: dict):
    response = client.post(
        "/api/v1/categories/",
        headers=shop_owner_headers,
        json={"name": "Gaming Consoles", "description": "PlayStation, Xbox, Nintendo"},
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "gaming-consoles"


def test_create_category_customer_forbidden(client: TestClient, customer_headers: dict):
    response = client.post(
        "/api/v1/categories/",
        headers=customer_headers,
        json={"name": "Smart Home", "description": "IoT devices"},
    )
    assert response.status_code == 403


def test_list_products_pagination_and_search(client: TestClient, test_product):
    response = client.get("/api/v1/products/?search=Headphones&page=1&size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Wireless Noise-Canceling Headphones"
    assert data["items"][0]["category"]["slug"] == "electronics"


def test_create_product_shop_owner(client: TestClient, shop_owner_headers: dict, test_category):
    response = client.post(
        "/api/v1/products/",
        headers=shop_owner_headers,
        json={
            "name": "Mechanical Keyboard",
            "description": "RGB Backlit keyboard",
            "price": "99.99",
            "stock": 15,
            "category_id": test_category.id,
            "is_active": True,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Mechanical Keyboard"
    assert data["category"]["name"] == "Electronics"


def test_delete_category_blocked_with_products(client: TestClient, admin_headers: dict, test_category, test_product):
    # Attempting to delete category that contains test_product
    response = client.delete(f"/api/v1/categories/{test_category.id}", headers=admin_headers)
    assert response.status_code == 400
    assert "contains" in response.json()["detail"]
