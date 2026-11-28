from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import ProductResponse


# Base cart item attributes
class CartItemBase(BaseModel):
    product_id: int = Field(..., gt=0, examples=[1])
    quantity: int = Field(default=1, ge=1, le=100, examples=[2])


# Schema for adding an item to the cart
class CartItemCreate(CartItemBase):
    pass


# Schema for updating the quantity of an existing cart item
class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=1, le=100, examples=[3])


# Schema for returning an item in the cart (includes nested product details and computed subtotal)
class CartItemResponse(BaseModel):
    id: int
    cart_id: int
    product_id: int
    quantity: int
    product: ProductResponse
    subtotal: Decimal = Field(..., ge=Decimal("0.00"), examples=[Decimal("199.98")])

    # Pydantic v2: allows reading directly from SQLAlchemy ORM models
    model_config = ConfigDict(from_attributes=True)


# Schema for returning the complete active shopping cart
class CartResponse(BaseModel):
    id: int
    user_id: int
    items: list[CartItemResponse] = []
    total_items: int = Field(default=0, ge=0, examples=[3])
    total_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), examples=[Decimal("299.97")])
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
