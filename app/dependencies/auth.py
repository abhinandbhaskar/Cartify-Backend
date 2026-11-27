import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.database.connection import get_db
from app.models.user import User, UserRole
from app.services.user_service import get_user_by_id

# OAuth2 scheme: tells Swagger UI to display the 'Authorize' lock button and look for 'Authorization: Bearer <token>'
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that:
    1. Extracts the Bearer JWT token from the HTTP Authorization header.
    2. Decodes and verifies the token signature and expiration.
    3. Retrieves the authenticated User from the database by user ID.
    4. Validates that the account is active.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        subject: str | None = payload.get("sub")
        if subject is None:
            raise credentials_exception
        user_id = int(subject)
    except (jwt.PyJWTError, ValueError):
        raise credentials_exception

    user = get_user_by_id(db, user_id=user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Role-Based Access Control (RBAC) guard:
    Ensures the authenticated user has the ADMIN role.
    Raises 403 Forbidden for non-admins.
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges (Admin required)",
        )
    return current_user


def require_shop_owner(current_user: User = Depends(get_current_user)) -> User:
    """
    Role-Based Access Control (RBAC) guard:
    Ensures the authenticated user has either the SHOP_OWNER or ADMIN role.
    Raises 403 Forbidden otherwise.
    """
    if current_user.role not in [UserRole.SHOP_OWNER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges (Shop Owner required)",
        )
    return current_user
