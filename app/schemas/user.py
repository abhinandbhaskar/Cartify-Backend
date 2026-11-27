from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.user import UserRole


# 1. Base schema with shared fields
class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, examples=["John Doe"])
    email: EmailStr = Field(..., examples=["john@example.com"])
    role: UserRole = Field(default=UserRole.CUSTOMER, examples=[UserRole.CUSTOMER])


# 2. Registration request schema (requires password)
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128, description="Plaintext password (min 6 characters)")


# 3. Login request schema
class UserLogin(BaseModel):
    email: EmailStr = Field(..., examples=["john@example.com"])
    password: str = Field(..., min_length=1)


# 4. Profile update request schema
class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=6, max_length=128)


# 5. Public response schema (safely excludes password_hash)
class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime

    # In Pydantic v2, from_attributes=True enables reading directly from SQLAlchemy ORM models
    model_config = ConfigDict(from_attributes=True)


# 6. JWT Token response on login
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# 7. Internal token payload schema
class TokenPayload(BaseModel):
    sub: str | None = None
    exp: int | None = None
