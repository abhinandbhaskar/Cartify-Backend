from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.order import Order
from app.models.payment import Payment
from app.schemas.order import OrderStatus
from app.schemas.payment import (
    PaymentInitiateRequest,
    PaymentStatus,
    PaymentVerifyRequest,
)


def initiate_payment(
    db: Session,
    user_id: int,
    initiate_in: PaymentInitiateRequest,
) -> Payment:
    """
    Initiate a payment session for an order:
    1. Validates that the order exists and belongs to the authenticated customer.
    2. Validates that the order is in 'pending' status (cannot pay for paid or cancelled orders).
    3. If an existing pending payment record exists for this order, reuses it.
    4. Otherwise, creates a new Payment record in 'pending' status.
    5. Commits and returns the payment session.
    """
    order = db.scalar(
        select(Order).where(Order.id == initiate_in.order_id, Order.user_id == user_id)
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {initiate_in.order_id} not found.",
        )

    if order.status == OrderStatus.PAID.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has already been paid.",
        )

    if order.status == OrderStatus.CANCELLED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot initiate payment for a cancelled order.",
        )

    # Check for an existing pending payment record for this order
    existing_payment = db.scalar(
        select(Payment)
        .where(Payment.order_id == order.id, Payment.status == PaymentStatus.PENDING.value)
        .order_by(Payment.id.desc())
    )
    if existing_payment:
        existing_payment.provider = initiate_in.provider.value
        existing_payment.amount = order.total_amount
        db.commit()
        db.refresh(existing_payment)
        return existing_payment

    payment = Payment(
        order_id=order.id,
        provider=initiate_in.provider.value,
        amount=order.total_amount,
        status=PaymentStatus.PENDING.value,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return payment


def verify_payment(
    db: Session,
    user_id: int,
    verify_in: PaymentVerifyRequest,
    is_admin: bool = False,
) -> Payment:
    """
    Verify payment settlement:
    1. Validates payment and order ownership.
    2. Prevents transaction replay attacks (verifies transaction_id uniqueness).
    3. If status is SUCCESS:
       - Marks payment as 'success' and records transaction_id.
       - Atomically transitions order status to 'paid'.
    4. If status is FAILED:
       - Marks payment as 'failed'.
       - Leaves order as 'pending' so customer can retry payment.
    5. Commits and returns updated Payment.
    """
    stmt = (
        select(Payment)
        .options(joinedload(Payment.order))
        .where(Payment.id == verify_in.payment_id)
    )
    payment = db.scalar(stmt)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment record with id {verify_in.payment_id} not found.",
        )

    if not is_admin and payment.order.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment record with id {verify_in.payment_id} not found.",
        )

    # Already settled
    if payment.status == PaymentStatus.SUCCESS.value:
        return payment

    # Prevent transaction_id replay across different payments
    existing_txn = db.scalar(
        select(Payment).where(
            Payment.transaction_id == verify_in.transaction_id,
            Payment.id != payment.id,
        )
    )
    if existing_txn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction ID '{verify_in.transaction_id}' has already been used.",
        )

    payment.transaction_id = verify_in.transaction_id

    if verify_in.status == PaymentStatus.SUCCESS:
        payment.status = PaymentStatus.SUCCESS.value
        # Atomic order transition: pending -> paid
        payment.order.status = OrderStatus.PAID.value
    else:
        payment.status = PaymentStatus.FAILED.value
        # Order remains 'pending' allowing retry

    db.commit()
    db.refresh(payment)

    return payment


def get_payment_by_id(
    db: Session,
    payment_id: int,
    user_id: int,
    is_admin: bool = False,
) -> Payment:
    """Retrieve a single payment record with ownership enforcement."""
    stmt = (
        select(Payment)
        .options(joinedload(Payment.order))
        .where(Payment.id == payment_id)
    )
    payment = db.scalar(stmt)
    if not payment or (not is_admin and payment.order.user_id != user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment record with id {payment_id} not found.",
        )
    return payment


def get_order_payments(
    db: Session,
    order_id: int,
    user_id: int,
    is_admin: bool = False,
) -> list[Payment]:
    """Retrieve all payment attempts associated with a specific order."""
    order = db.scalar(select(Order).where(Order.id == order_id))
    if not order or (not is_admin and order.user_id != user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id {order_id} not found.",
        )

    stmt = select(Payment).where(Payment.order_id == order_id).order_by(Payment.id.desc())
    return list(db.scalars(stmt).all())
