from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.schemas.cart import (
    CartItemCreate,
    CartItemResponse,
    CartItemUpdate,
    CartResponse,
)
from app.schemas.product import ProductResponse


def get_or_create_cart(db: Session, user_id: int) -> Cart:
    """
    Retrieve the active cart for a user.
    If no cart exists yet, automatically create and return a new one.
    """
    stmt = select(Cart).where(Cart.user_id == user_id)
    cart = db.scalar(stmt)
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def get_cart_details(db: Session, user_id: int) -> CartResponse:
    """
    Retrieve full cart details for a user:
    1. Eagerly loads items, products, and categories in a single query to eliminate N+1 queries.
    2. Calculates dynamic line item subtotals (quantity * live price).
    3. Calculates total_items and grand total_amount.
    """
    # Ensure cart exists
    get_or_create_cart(db, user_id=user_id)

    # Eagerly load cart -> items -> product -> category
    stmt = (
        select(Cart)
        .options(
            joinedload(Cart.items)
            .joinedload(CartItem.product)
            .joinedload(Product.category)
        )
        .where(Cart.user_id == user_id)
    )
    cart = db.scalar(stmt)
    assert cart is not None

    item_responses: list[CartItemResponse] = []
    total_items = 0
    total_amount = Decimal("0.00")

    for item in cart.items:
        product_resp = ProductResponse.model_validate(item.product)
        subtotal = item.product.price * item.quantity

        item_responses.append(
            CartItemResponse(
                id=item.id,
                cart_id=item.cart_id,
                product_id=item.product_id,
                quantity=item.quantity,
                product=product_resp,
                subtotal=subtotal,
            )
        )
        total_items += item.quantity
        total_amount += subtotal

    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        items=item_responses,
        total_items=total_items,
        total_amount=total_amount,
        updated_at=cart.updated_at,
    )


def add_item_to_cart(
    db: Session,
    user_id: int,
    item_in: CartItemCreate,
) -> CartResponse:
    """
    Add a product to the user's cart:
    1. Validates that the product exists and is active.
    2. Checks if requested quantity is within available stock.
    3. If the item already exists in the cart, increments the quantity (checking combined stock).
    4. If new, creates a new CartItem record.
    5. Returns updated CartResponse.
    """
    product = db.scalar(select(Product).where(Product.id == item_in.product_id))
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {item_in.product_id} not found.",
        )

    if not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product '{product.name}' is currently unavailable.",
        )

    if product.stock <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product '{product.name}' is out of stock.",
        )

    cart = get_or_create_cart(db, user_id=user_id)

    # Check if this product is already in the user's cart
    item_stmt = select(CartItem).where(
        CartItem.cart_id == cart.id,
        CartItem.product_id == item_in.product_id,
    )
    existing_item = db.scalar(item_stmt)

    if existing_item:
        new_quantity = existing_item.quantity + item_in.quantity
        if new_quantity > product.stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot add {item_in.quantity} more unit(s). "
                    f"Only {product.stock} available in stock (you already have {existing_item.quantity} in your cart)."
                ),
            )
        existing_item.quantity = new_quantity
    else:
        if item_in.quantity > product.stock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot add {item_in.quantity} unit(s). Only {product.stock} available in stock.",
            )
        new_item = CartItem(
            cart_id=cart.id,
            product_id=item_in.product_id,
            quantity=item_in.quantity,
        )
        db.add(new_item)

    cart.updated_at = func.now()
    db.commit()

    return get_cart_details(db, user_id=user_id)


def update_cart_item_quantity(
    db: Session,
    user_id: int,
    item_id: int,
    item_update: CartItemUpdate,
) -> CartResponse:
    """
    Update the quantity of an existing item in the user's cart:
    1. Validates that the cart item belongs to the authenticated user.
    2. Re-validates that the new quantity is within current product stock.
    3. Updates quantity, commits, and returns updated CartResponse.
    """
    cart = get_or_create_cart(db, user_id=user_id)

    stmt = (
        select(CartItem)
        .options(joinedload(CartItem.product))
        .where(CartItem.id == item_id, CartItem.cart_id == cart.id)
    )
    cart_item = db.scalar(stmt)
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart item with id {item_id} not found in your cart.",
        )

    if item_update.quantity > cart_item.product.stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot update quantity to {item_update.quantity}. "
                f"Only {cart_item.product.stock} available in stock."
            ),
        )

    cart_item.quantity = item_update.quantity
    cart.updated_at = func.now()
    db.commit()

    return get_cart_details(db, user_id=user_id)


def remove_cart_item(
    db: Session,
    user_id: int,
    item_id: int,
) -> CartResponse:
    """
    Remove a specific item from the user's cart:
    1. Enforces ownership: verifies the item belongs to the user's cart.
    2. Deletes the item and returns updated CartResponse.
    """
    cart = get_or_create_cart(db, user_id=user_id)

    stmt = select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id)
    cart_item = db.scalar(stmt)
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cart item with id {item_id} not found in your cart.",
        )

    db.delete(cart_item)
    cart.updated_at = func.now()
    db.commit()

    return get_cart_details(db, user_id=user_id)


def clear_cart(db: Session, user_id: int) -> None:
    """
    Remove all items from the user's active shopping cart.
    """
    cart = get_or_create_cart(db, user_id=user_id)

    stmt = select(CartItem).where(CartItem.cart_id == cart.id)
    items = db.scalars(stmt).all()
    for item in items:
        db.delete(item)

    cart.updated_at = func.now()
    db.commit()
