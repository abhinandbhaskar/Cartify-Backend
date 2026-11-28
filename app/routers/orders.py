from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.auth import get_current_user, require_admin, require_shop_owner
from app.models.user import User, UserRole
from app.schemas.order import (
    OrderCreate,
    OrderPaginationResponse,
    OrderResponse,
    OrderStatus,
    OrderStatusUpdate,
)
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post(
    "/checkout",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place an order from active shopping cart",
)
def checkout(
    order_in: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Atomic checkout:
    1. Validates delivery address from user's address book.
    2. Re-verifies product availability and inventory stock.
    3. Deducts product stock.
    4. Creates Order and OrderItem records snapshotting unit prices and shipping address.
    5. Clears the user's active shopping cart.
    """
    return order_service.create_order_from_cart(
        db=db, user_id=current_user.id, order_in=order_in
    )


@router.get(
    "/",
    response_model=OrderPaginationResponse,
    summary="Get order history for current user",
)
def list_my_orders(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderPaginationResponse:
    """Retrieve paginated order history for the authenticated customer."""
    return order_service.list_user_orders(
        db=db, user_id=current_user.id, page=page, size=size
    )


@router.get(
    "/admin/all",
    response_model=OrderPaginationResponse,
    summary="Admin: List all orders across all customers",
)
def list_all_orders_admin(
    status_filter: OrderStatus | None = Query(None, description="Filter orders by status"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OrderPaginationResponse:
    """Admin-only overview: Browse and filter all orders across the platform."""
    return order_service.list_all_orders(
        db=db, status_filter=status_filter, page=page, size=size
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order details by ID",
)
def get_order_details(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Retrieve order details with line items and product information.
    Customers can only view their own orders; Admins can view any order.
    """
    is_admin = current_user.role == UserRole.ADMIN
    order = order_service.get_order_by_id(
        db=db,
        order_id=order_id,
        user_id=None if is_admin else current_user.id,
    )
    return order_service.to_order_response(order)


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Cancel an order and restore inventory",
)
def cancel_order_endpoint(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Cancel an order:
    - Only allowed if order is in 'pending' or 'paid' status.
    - Automatically restores deducted stock quantities back to product inventory.
    - Customers can cancel their own orders; Admins can cancel any eligible order.
    """
    is_admin = current_user.role == UserRole.ADMIN
    return order_service.cancel_order(
        db=db,
        order_id=order_id,
        user_id=None if is_admin else current_user.id,
        is_admin=is_admin,
    )


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse,
    summary="Update order lifecycle status",
)
def update_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    current_user: User = Depends(require_shop_owner),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Update order lifecycle state (e.g. pending -> paid -> shipped -> delivered).
    Requires Shop Owner or Admin role.
    """
    return order_service.update_order_status(
        db=db, order_id=order_id, new_status=status_update.status
    )
