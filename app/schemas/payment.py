from datetime import datetime
from decimal import Decimal
import enum
from pydantic import BaseModel, ConfigDict, Field


# Supported payment providers / gateways
class PaymentProvider(str, enum.Enum):
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    MOCK = "mock_gateway"
    COD = "cash_on_delivery"


# Payment transaction status
class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


# Request schema for initiating a payment session for an order
class PaymentInitiateRequest(BaseModel):
    order_id: int = Field(..., gt=0, examples=[1], description="ID of the pending order to pay for")
    provider: PaymentProvider = Field(
        default=PaymentProvider.MOCK,
        examples=[PaymentProvider.MOCK],
        description="Payment gateway provider",
    )


# Request schema for verifying a completed payment transaction
class PaymentVerifyRequest(BaseModel):
    payment_id: int = Field(..., gt=0, examples=[1], description="ID of the initiated payment record")
    transaction_id: str = Field(
        ...,
        min_length=3,
        max_length=150,
        examples=["txn_mock_1234567890"],
        description="Gateway transaction / payment ID reference",
    )
    status: PaymentStatus = Field(
        default=PaymentStatus.SUCCESS,
        examples=[PaymentStatus.SUCCESS],
        description="Payment outcome (success or failed)",
    )


# Response schema returning payment transaction details
class PaymentResponse(BaseModel):
    id: int
    order_id: int
    provider: str
    transaction_id: str | None = None
    amount: Decimal = Field(..., ge=Decimal("0.00"), decimal_places=2, max_digits=10)
    status: PaymentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
