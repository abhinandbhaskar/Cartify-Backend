from fastapi.testclient import TestClient


def test_get_empty_cart_auto_provisioned(client: TestClient, customer_headers: dict):
    response = client.get("/api/v1/cart/", headers=customer_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_items"] == 0
    assert data["total_amount"] == "0.00"
    assert len(data["items"]) == 0


def test_add_item_to_cart_and_duplicate_merge(client: TestClient, customer_headers: dict, test_product):
    # 1. Add 2 units
    response = client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 2},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["total_items"] == 2
    assert data["total_amount"] == "399.98"
    assert len(data["items"]) == 1
    assert data["items"][0]["product"]["name"] == "Wireless Noise-Canceling Headphones"

    # 2. Add 1 more unit of same product -> merges into single line item with quantity 3
    response2 = client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 1},
    )
    assert response2.status_code == 201
    data2 = response2.json()
    assert data2["total_items"] == 3
    assert data2["total_amount"] == "599.97"
    assert len(data2["items"]) == 1
    assert data2["items"][0]["quantity"] == 3


def test_add_item_exceeding_stock_fails(client: TestClient, customer_headers: dict, test_product):
    # test_product has stock = 20
    response = client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 50},
    )
    assert response.status_code == 400
    assert "stock" in response.json()["detail"].lower()


def test_update_cart_item_quantity(client: TestClient, customer_headers: dict, test_product):
    # Add item
    add_res = client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 2},
    )
    item_id = add_res.json()["items"][0]["id"]

    # Update to 5 units
    up_res = client.put(
        f"/api/v1/cart/items/{item_id}",
        headers=customer_headers,
        json={"quantity": 5},
    )
    assert up_res.status_code == 200
    data = up_res.json()
    assert data["total_items"] == 5
    assert data["total_amount"] == "999.95"


def test_remove_cart_item_and_clear_cart(client: TestClient, customer_headers: dict, test_product):
    # Add item
    add_res = client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 2},
    )
    item_id = add_res.json()["items"][0]["id"]

    # Remove item
    del_res = client.delete(f"/api/v1/cart/items/{item_id}", headers=customer_headers)
    assert del_res.status_code == 200
    assert del_res.json()["total_items"] == 0

    # Add again and clear cart
    client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 2},
    )
    clear_res = client.delete("/api/v1/cart/", headers=customer_headers)
    assert clear_res.status_code == 200
    assert "cleared successfully" in clear_res.json()["message"]
