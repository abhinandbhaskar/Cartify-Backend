from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.cart import (
    CartItemCreate,
    CartItemUpdate,
    CartResponse,
)
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get(
    "/",
    response_model=CartResponse,
    summary="Get current user's shopping cart",
)
def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartResponse:
    """
    Retrieve the authenticated user's active shopping cart,
    including all items, live product pricing, line item subtotals, and cart totals.
    """
    return cart_service.get_cart_details(db=db, user_id=current_user.id)


@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to the shopping cart",
)
def add_item_to_cart(
    item_in: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartResponse:
    """
    Add a product to the user's cart:
    - Verifies product existence, active status, and available stock.
    - If the product is already in the cart, increments quantity.
    - Returns the updated shopping cart.
    """
    return cart_service.add_item_to_cart(
        db=db, user_id=current_user.id, item_in=item_in
    )


@router.put(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Update the quantity of a cart item",
)
def update_cart_item(
    item_id: int,
    item_update: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartResponse:
    """
    Update the quantity of an item in the user's cart:
    - Enforces ownership: verifies the item belongs to the authenticated user.
    - Validates requested quantity against current available stock.
    - Returns the updated shopping cart.
    """
    return cart_service.update_cart_item_quantity(
        db=db, user_id=current_user.id, item_id=item_id, item_update=item_update
    )


@router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Remove an item from the shopping cart",
)
def remove_cart_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartResponse:
    """
    Remove a specific item from the user's cart:
    - Enforces ownership: verifies the item belongs to the authenticated user.
    - Deletes the line item and recalculates cart totals.
    """
    return cart_service.remove_cart_item(
        db=db, user_id=current_user.id, item_id=item_id
    )


@router.delete(
    "/",
    summary="Clear the shopping cart",
)
def clear_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Remove all items from the user's active shopping cart.
    """
    cart_service.clear_cart(db=db, user_id=current_user.id)
    return {"message": "Shopping cart cleared successfully"}
