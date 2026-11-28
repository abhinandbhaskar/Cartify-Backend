from decimal import Decimal
import math
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.address import Address
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.schemas.order import (
    OrderCreate,
    OrderItemResponse,
    OrderPaginationResponse,
    OrderResponse,
    OrderStatus,
)
from app.schemas.product import ProductResponse


def format_address_snapshot(address: Address) -> str:
    """
    Format address into an immutable historical string snapshot at checkout.
    e.g. 'Jane Doe, Phone: +91-9876543210, 123 MG Road, Bangalore, Karnataka - 560001, India'
    """
    return (
        f"{address.full_name}, Phone: {address.phone}, "
        f"{address.street}, {address.city}, {address.state} - {address.postal_code}, {address.country}"
    )


def to_order_response(order: Order) -> OrderResponse:
    """
    Convert an SQLAlchemy Order ORM model into a validated OrderResponse schema.
    Computes line item subtotals (quantity * unit_price snapshot) and serializes nested product.
    """
    item_responses = [
        OrderItemResponse(
            id=item.id,
            order_id=item.order_id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            subtotal=item.unit_price * item.quantity,
            product=ProductResponse.model_validate(item.product) if item.product else None,
        )
        for item in order.items
    ]
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=OrderStatus(order.status),
        total_amount=order.total_amount,
        shipping_address=order.shipping_address,
        created_at=order.created_at,
        items=item_responses,
    )


def get_order_by_id(
    db: Session,
    order_id: int,
    user_id: int | None = None,
) -> Order:
    """
    Retrieve an order with eagerly loaded items, products, and categories.
    If user_id is provided, enforces that the order belongs to that user (ownership isolation).
    """
    stmt = (
        select(Order)
        .options(
            joinedload(Order.items)
            .joinedload(OrderItem.product)
            .joinedload(Product.category)
        )
        .where(Order.id == order_id)
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)

    order = db.scalar(stmt)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found.",
        )
    return order


def create_order_from_cart(
    db: Session,
    user_id: int,
    order_in: OrderCreate,
) -> OrderResponse:
    """
    Execute atomic checkout from the user's active shopping cart:
    1. Validates that the selected shipping address exists and belongs to the user.
    2. Builds an immutable text snapshot of the address.
    3. Fetches cart items: rejects if cart is empty.
    4. Re-validates real-time inventory and active status for every item.
    5. Deducts inventory (product.stock -= quantity).
    6. Creates Order and OrderItem records snapshotting unit_price.
    7. Clears all items from the user's shopping cart.
    8. Commits the transaction atomically.
    """
    # 1. Address validation & snapshot
    addr_stmt = select(Address).where(
        Address.id == order_in.address_id, Address.user_id == user_id
    )
    address = db.scalar(addr_stmt)
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shipping address with id {order_in.address_id} not found in your address book.",
        )
    address_snapshot = format_address_snapshot(address)

    # 2. Fetch cart with items and products
    cart_stmt = (
        select(Cart)
        .options(joinedload(Cart.items).joinedload(CartItem.product))
        .where(Cart.user_id == user_id)
    )
    cart = db.scalar(cart_stmt)
    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot place an order with an empty shopping cart.",
        )

    # 3. Stock validation & inventory deduction
    order_items: list[OrderItem] = []
    total_amount = Decimal("0.00")

    for cart_item in cart.items:
        product = cart_item.product
        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{product.name if product else cart_item.product_id}' is no longer available.",
            )

        if product.stock < cart_item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock}, requested in cart: {cart_item.quantity}."
                ),
            )

        # Deduct inventory atomically
        product.stock -= cart_item.quantity

        unit_price = product.price
        line_subtotal = unit_price * cart_item.quantity
        total_amount += line_subtotal

        order_item = OrderItem(
            product_id=product.id,
            quantity=cart_item.quantity,
            unit_price=unit_price,
        )
        order_items.append(order_item)

    # 4. Create Order with items
    db_order = Order(
        user_id=user_id,
        status=OrderStatus.PENDING.value,
        total_amount=total_amount,
        shipping_address=address_snapshot,
        items=order_items,
    )
    db.add(db_order)

    # 5. Clear cart
    for cart_item in list(cart.items):
        db.delete(cart_item)
    cart.updated_at = func.now()

    # 6. Commit transaction atomically
    db.commit()
    db.refresh(db_order)

    full_order = get_order_by_id(db, order_id=db_order.id, user_id=user_id)
    return to_order_response(full_order)


def list_user_orders(
    db: Session,
    user_id: int,
    page: int = 1,
    size: int = 10,
) -> OrderPaginationResponse:
    """
    Retrieve a paginated history of orders belonging to the authenticated customer.
    """
    count_stmt = select(func.count(Order.id)).where(Order.user_id == user_id)
    total = db.scalar(count_stmt) or 0
    pages = math.ceil(total / size) if total > 0 else 0

    offset = (page - 1) * size
    stmt = (
        select(Order)
        .options(
            joinedload(Order.items)
            .joinedload(OrderItem.product)
            .joinedload(Product.category)
        )
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
        .offset(offset)
        .limit(size)
    )
    orders = list(db.scalars(stmt).unique().all())

    return OrderPaginationResponse(
        items=[to_order_response(o) for o in orders],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


def list_all_orders(
    db: Session,
    status_filter: OrderStatus | None = None,
    page: int = 1,
    size: int = 10,
) -> OrderPaginationResponse:
    """
    Admin overview: Retrieve all orders across all customers with optional status filter.
    """
    conditions = []
    if status_filter:
        conditions.append(Order.status == status_filter.value)

    count_stmt = select(func.count(Order.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0
    pages = math.ceil(total / size) if total > 0 else 0

    offset = (page - 1) * size
    stmt = (
        select(Order)
        .options(
            joinedload(Order.items)
            .joinedload(OrderItem.product)
            .joinedload(Product.category)
        )
    )
    if conditions:
        stmt = stmt.where(*conditions)

    stmt = stmt.order_by(Order.id.desc()).offset(offset).limit(size)
    orders = list(db.scalars(stmt).unique().all())

    return OrderPaginationResponse(
        items=[to_order_response(o) for o in orders],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


def cancel_order(
    db: Session,
    order_id: int,
    user_id: int | None = None,
    is_admin: bool = False,
) -> OrderResponse:
    """
    Cancel an order:
    1. Validates ownership (unless caller is admin).
    2. Validates order status allows cancellation (cannot cancel already shipped/delivered/cancelled orders).
    3. Restores deducted inventory back to products (product.stock += quantity).
    4. Sets order status to 'cancelled' and commits.
    """
    order = get_order_by_id(db, order_id=order_id, user_id=None if is_admin else user_id)

    if order.status == OrderStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order is already cancelled.",
        )

    if order.status in [OrderStatus.SHIPPED.value, OrderStatus.DELIVERED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel order with status '{order.status}'. Items have already been dispatched.",
        )

    # Restore inventory back to products
    for item in order.items:
        product_stmt = select(Product).where(Product.id == item.product_id)
        product = db.scalar(product_stmt)
        if product:
            product.stock += item.quantity

    order.status = OrderStatus.CANCELLED.value
    db.commit()
    db.refresh(order)

    return to_order_response(order)


def update_order_status(
    db: Session,
    order_id: int,
    new_status: OrderStatus,
) -> OrderResponse:
    """
    Admin / Merchant lifecycle transition:
    If transitioning to CANCELLED, delegates to cancel_order to restore stock.
    Otherwise updates status and commits.
    """
    if new_status == OrderStatus.CANCELLED:
        return cancel_order(db, order_id=order_id, is_admin=True)

    order = get_order_by_id(db, order_id=order_id)
    if order.status == OrderStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update status of an already cancelled order.",
        )

    order.status = new_status.value
    db.commit()
    db.refresh(order)

    return to_order_response(order)
