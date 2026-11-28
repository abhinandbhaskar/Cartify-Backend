from pydantic import BaseModel, ConfigDict, Field


# Base address attributes
class AddressBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, examples=["Jane Doe"])
    phone: str = Field(..., min_length=7, max_length=20, examples=["+91-9876543210"])
    street: str = Field(..., min_length=3, max_length=255, examples=["123 MG Road, Flat 4B"])
    city: str = Field(..., min_length=2, max_length=100, examples=["Bangalore"])
    state: str = Field(..., min_length=2, max_length=100, examples=["Karnataka"])
    postal_code: str = Field(..., min_length=3, max_length=20, examples=["560001"])
    country: str = Field(default="India", min_length=2, max_length=100, examples=["India"])
    is_default: bool = Field(default=False, examples=[True])


# Schema for creating a new delivery address
class AddressCreate(AddressBase):
    pass


# Schema for partially updating an existing delivery address
class AddressUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=100, examples=["Jane Doe"])
    phone: str | None = Field(None, min_length=7, max_length=20, examples=["+91-9876543210"])
    street: str | None = Field(None, min_length=3, max_length=255)
    city: str | None = Field(None, min_length=2, max_length=100)
    state: str | None = Field(None, min_length=2, max_length=100)
    postal_code: str | None = Field(None, min_length=3, max_length=20)
    country: str | None = Field(None, min_length=2, max_length=100)
    is_default: bool | None = Field(None, examples=[True])


# Schema for returning an address to clients
class AddressResponse(AddressBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)
