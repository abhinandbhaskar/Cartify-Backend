from datetime import datetime
from decimal import Decimal
import enum
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import ProductResponse


# Allowed order lifecycle states
class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


# Request payload for initiating checkout from cart
class OrderCreate(BaseModel):
    address_id: int = Field(
        ...,
        gt=0,
        examples=[1],
        description="ID of the delivery destination from user's address book",
    )


# Admin / Merchant payload for updating order lifecycle state
class OrderStatusUpdate(BaseModel):
    status: OrderStatus = Field(
        ...,
        examples=[OrderStatus.SHIPPED],
        description="Target order lifecycle status",
    )


# Schema representing an item within an order (immutable price snapshot)
class OrderItemResponse(BaseModel):
    id: int
    order_id: int
    product_id: int
    quantity: int
    unit_price: Decimal = Field(..., ge=Decimal("0.00"), decimal_places=2, max_digits=10)
    subtotal: Decimal = Field(..., ge=Decimal("0.00"), decimal_places=2, max_digits=10)
    product: ProductResponse | None = None

    model_config = ConfigDict(from_attributes=True)


# Schema representing a complete order with historical snapshots
class OrderResponse(BaseModel):
    id: int
    user_id: int
    status: OrderStatus
    total_amount: Decimal = Field(..., ge=Decimal("0.00"), decimal_places=2, max_digits=10)
    shipping_address: str = Field(
        ...,
        examples=["Jane Doe, +91-9876543210, 123 MG Road, Bangalore, Karnataka 560001, India"],
        description="Immutable snapshot of the shipping address at checkout",
    )
    created_at: datetime
    items: list[OrderItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


# Standard envelope for paginated order histories
class OrderPaginationResponse(BaseModel):
    items: list[OrderResponse]
    total: int = Field(..., ge=0, examples=[25])
    page: int = Field(..., ge=1, examples=[1])
    size: int = Field(..., ge=1, examples=[10])
    pages: int = Field(..., ge=0, examples=[3])

    model_config = ConfigDict(from_attributes=True)
