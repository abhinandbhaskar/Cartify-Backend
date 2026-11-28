from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentResponse,
    PaymentVerifyRequest,
)
from app.services import payment_service

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post(
    "/initiate",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate payment session for a pending order",
)
def initiate_payment(
    initiate_in: PaymentInitiateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """
    Generate a payment session for an order:
    - Enforces order ownership (must belong to authenticated user).
    - Verifies order is in 'pending' status.
    - Creates or reuses a payment record with the exact order total amount.
    """
    return payment_service.initiate_payment(
        db=db, user_id=current_user.id, initiate_in=initiate_in
    )


@router.post(
    "/verify",
    response_model=PaymentResponse,
    summary="Verify transaction and settle order",
)
def verify_payment(
    verify_in: PaymentVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """
    Verify payment settlement:
    - On 'success': marks payment as success and automatically transitions order status to 'paid'.
    - On 'failed': records payment failure and leaves order 'pending' for retry.
    - Enforces transaction ID replay protection.
    """
    is_admin = current_user.role == UserRole.ADMIN
    return payment_service.verify_payment(
        db=db,
        user_id=current_user.id,
        verify_in=verify_in,
        is_admin=is_admin,
    )


@router.get(
    "/order/{order_id}",
    response_model=list[PaymentResponse],
    summary="Get payment history for an order",
)
def get_order_payments(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PaymentResponse]:
    """
    Retrieve all payment records for a specific order.
    Customers can only view their own orders; Admins can view any order.
    """
    is_admin = current_user.role == UserRole.ADMIN
    return payment_service.get_order_payments(
        db=db,
        order_id=order_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )
