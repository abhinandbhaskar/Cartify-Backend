from decimal import Decimal
from fastapi.testclient import TestClient


def test_address_management_and_default_switching(client: TestClient, customer_headers: dict):
    # 1. First address auto-marked default
    res1 = client.post(
        "/api/v1/addresses/",
        headers=customer_headers,
        json={
            "full_name": "John Customer",
            "phone": "+91-9876543210",
            "street": "123 MG Road",
            "city": "Bangalore",
            "state": "Karnataka",
            "postal_code": "560001",
            "country": "India",
            "is_default": False,
        },
    )
    assert res1.status_code == 201
    addr1_id = res1.json()["id"]
    assert res1.json()["is_default"] is True

    # 2. Second address marked default -> unsets default on addr1
    res2 = client.post(
        "/api/v1/addresses/",
        headers=customer_headers,
        json={
            "full_name": "John Office",
            "phone": "+91-9876543210",
            "street": "456 Tech Park",
            "city": "Bangalore",
            "state": "Karnataka",
            "postal_code": "560066",
            "country": "India",
            "is_default": True,
        },
    )
    assert res2.status_code == 201
    assert res2.json()["is_default"] is True

    # Check addr1 is no longer default
    get1 = client.get(f"/api/v1/addresses/{addr1_id}", headers=customer_headers)
    assert get1.json()["is_default"] is False


def test_atomic_checkout_deducts_stock_and_clears_cart(
    client: TestClient, customer_headers: dict, test_product, test_address
):
    # 1. Add 2 headphones to cart (product stock is 20)
    client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 2},
    )

    # 2. Checkout
    order_res = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"address_id": test_address.id},
    )
    assert order_res.status_code == 201
    order_data = order_res.json()
    assert order_data["status"] == "pending"
    assert order_data["total_amount"] == "399.98"
    assert len(order_data["items"]) == 1
    assert order_data["items"][0]["unit_price"] == "199.99"
    order_id = order_data["id"]

    # 3. Product stock was deducted: 20 -> 18
    prod_check = client.get(f"/api/v1/products/{test_product.id}")
    assert prod_check.json()["stock"] == 18

    # 4. Cart was cleared
    cart_check = client.get("/api/v1/cart/", headers=customer_headers)
    assert cart_check.json()["total_items"] == 0

    return order_id


def test_price_snapshot_resilience(
    client: TestClient, customer_headers: dict, shop_owner_headers: dict, test_product, test_address
):
    # Checkout at $199.99
    client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 1},
    )
    order_res = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"address_id": test_address.id},
    )
    order_id = order_res.json()["id"]
    assert order_res.json()["total_amount"] == "199.99"

    # Merchant changes product price to $299.99
    client.put(
        f"/api/v1/products/{test_product.id}",
        headers=shop_owner_headers,
        json={"price": "299.99"},
    )

    # Historical order must still report unit_price = 199.99 and total = 199.99!
    refetched = client.get(f"/api/v1/orders/{order_id}", headers=customer_headers)
    assert refetched.json()["total_amount"] == "199.99"
    assert refetched.json()["items"][0]["unit_price"] == "199.99"


def test_order_cancellation_restores_inventory(
    client: TestClient, customer_headers: dict, test_product, test_address
):
    # Initial stock is 20
    client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 3},
    )
    order_res = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"address_id": test_address.id},
    )
    order_id = order_res.json()["id"]

    # Stock is now 17
    assert client.get(f"/api/v1/products/{test_product.id}").json()["stock"] == 17

    # Cancel order
    cancel_res = client.post(f"/api/v1/orders/{order_id}/cancel", headers=customer_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # Stock is restored to 20!
    assert client.get(f"/api/v1/products/{test_product.id}").json()["stock"] == 20


def test_payment_initiation_and_successful_settlement(
    client: TestClient, customer_headers: dict, test_product, test_address
):
    # Create order
    client.post(
        "/api/v1/cart/items",
        headers=customer_headers,
        json={"product_id": test_product.id, "quantity": 1},
    )
    order_res = client.post(
        "/api/v1/orders/checkout",
        headers=customer_headers,
        json={"address_id": test_address.id},
    )
    order_id = order_res.json()["id"]

    # 1. Initiate Payment Session
    pay_init = client.post(
        "/api/v1/payments/initiate",
        headers=customer_headers,
        json={"order_id": order_id, "provider": "mock_gateway"},
    )
    assert pay_init.status_code == 201
    payment_id = pay_init.json()["id"]
    assert pay_init.json()["status"] == "pending"
    assert pay_init.json()["amount"] == "199.99"

    # 2. Verify Payment (Success)
    pay_ver = client.post(
        "/api/v1/payments/verify",
        headers=customer_headers,
        json={
            "payment_id": payment_id,
            "transaction_id": "txn_test_live_123",
            "status": "success",
        },
    )
    assert pay_ver.status_code == 200
    assert pay_ver.json()["status"] == "success"

    # 3. Check Order automatically transitioned to PAID!
    order_check = client.get(f"/api/v1/orders/{order_id}", headers=customer_headers)
    assert order_check.json()["status"] == "paid"
