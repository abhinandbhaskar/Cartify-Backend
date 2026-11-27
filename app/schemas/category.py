from pydantic import BaseModel, ConfigDict, Field


# Base shared attributes
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["Electronics"])
    description: str | None = Field(None, max_length=500, examples=["Gadgets, devices, and accessories"])


# Schema for creating a category (slug is auto-generated in service)
class CategoryCreate(CategoryBase):
    pass


# Schema for updating a category (all fields optional)
class CategoryUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100, examples=["Consumer Electronics"])
    description: str | None = Field(None, max_length=500)


# Response schema returned to clients
class CategoryResponse(CategoryBase):
    id: int
    slug: str

    # Pydantic v2: enables reading directly from SQLAlchemy ProductCategory models
    model_config = ConfigDict(from_attributes=True)
