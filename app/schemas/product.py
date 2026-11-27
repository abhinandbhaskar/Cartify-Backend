from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoryResponse


# Base product attributes shared across schemas
class ProductBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, examples=["Wireless Noise-Canceling Headphones"])
    description: str | None = Field(None, max_length=5000, examples=["Premium over-ear headphones with 30-hour battery life."])
    price: Decimal = Field(..., gt=Decimal("0.00"), decimal_places=2, max_digits=10, examples=[Decimal("99.99")])
    stock: int = Field(default=0, ge=0, examples=[50])
    image_url: str | None = Field(None, max_length=500, examples=["https://example.com/images/headphones.jpg"])
    category_id: int = Field(..., gt=0, examples=[1])


# Schema for creating a product (is_active defaults to True)
class ProductCreate(ProductBase):
    is_active: bool = Field(default=True, examples=[True])


# Schema for updating a product (all fields optional for partial updates)
class ProductUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200, examples=["Wireless Noise-Canceling Headphones v2"])
    description: str | None = Field(None, max_length=5000)
    price: Decimal | None = Field(None, gt=Decimal("0.00"), decimal_places=2, max_digits=10, examples=[Decimal("89.99")])
    stock: int | None = Field(None, ge=0, examples=[100])
    image_url: str | None = Field(None, max_length=500)
    category_id: int | None = Field(None, gt=0, examples=[2])
    is_active: bool | None = Field(None, examples=[True])


# Schema for returning product data to clients (includes category details and DB metadata)
class ProductResponse(ProductBase):
    id: int
    is_active: bool
    created_at: datetime
    category: CategoryResponse | None = None

    # Pydantic v2: enables reading directly from SQLAlchemy Product ORM models
    model_config = ConfigDict(from_attributes=True)


# Standardized pagination wrapper for product list endpoints
class ProductPaginationResponse(BaseModel):
    items: list[ProductResponse]
    total: int = Field(..., ge=0, examples=[42])
    page: int = Field(..., ge=1, examples=[1])
    size: int = Field(..., ge=1, examples=[10])
    pages: int = Field(..., ge=0, examples=[5])

    model_config = ConfigDict(from_attributes=True)
