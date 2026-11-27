from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def get_user_by_email(db: Session, email: str) -> User | None:
    """Retrieve a user by their email address."""
    stmt = select(User).where(User.email == email)
    return db.scalar(stmt)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Retrieve a user by their unique primary key ID."""
    stmt = select(User).where(User.id == user_id)
    return db.scalar(stmt)


def register_user(db: Session, user_in: UserCreate) -> User:
    """
    Register a new user:
    1. Validates that the email is not already registered.
    2. Hashes the plaintext password using Bcrypt.
    3. Persists the new User record into the database.
    """
    existing_user = get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    db_user = User(
        name=user_in.name,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
        role=user_in.role,
        is_active=True,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    Authenticate a user by email and password:
    1. Verifies that a user with the given email exists.
    2. Verifies that the provided password matches the stored Bcrypt hash.
    3. Verifies that the user account is active.
    """
    user = get_user_by_email(db, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive. Please contact support.",
        )

    return user


def update_user(db: Session, db_user: User, user_update: UserUpdate) -> User:
    """
    Update an existing user's profile information:
    Supports updating name, email (with duplicate check), and password (re-hashed).
    """
    if user_update.name is not None:
        db_user.name = user_update.name

    if user_update.email is not None and user_update.email != db_user.email:
        existing = get_user_by_email(db, user_update.email)
        if existing and existing.id != db_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email address is already in use.",
            )
        db_user.email = user_update.email

    if user_update.password is not None:
        db_user.password_hash = hash_password(user_update.password)

    db.commit()
    db.refresh(db_user)
    return db_user
