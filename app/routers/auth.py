from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.connection import get_db
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.user_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new customer account (hashes password and stores in database)."""
    return register_user(db=db, user_in=user_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and get JWT access token",
)
def login(
    login_in: UserLogin,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate user credentials and return a signed Bearer JWT access token."""
    user = authenticate_user(db=db, email=login_in.email, password=login_in.password)
    access_token = create_access_token(subject=user.id)
    return TokenResponse(access_token=access_token, token_type="bearer")
