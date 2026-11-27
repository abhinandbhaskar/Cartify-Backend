from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from app.core.config import settings

# Initialize password hasher with Bcrypt algorithm
password_hash = PasswordHash((BcryptHasher(),))


def hash_password(password: str) -> str:
    """Hash a plaintext password using Bcrypt with an automatically generated salt."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an existing stored Bcrypt hash."""
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Create and return an encoded JWT access token with a subject claim and expiration."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }
    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and cryptographically verify a JWT access token using the application's SECRET_KEY."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
