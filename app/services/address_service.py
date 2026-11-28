from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.address import Address
from app.schemas.address import AddressCreate, AddressUpdate


def get_user_addresses(db: Session, user_id: int) -> list[Address]:
    """
    Retrieve all delivery destinations belonging to the user.
    Sorts default address first, followed by newest additions.
    """
    stmt = (
        select(Address)
        .where(Address.user_id == user_id)
        .order_by(Address.is_default.desc(), Address.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_address_by_id(db: Session, address_id: int, user_id: int) -> Address:
    """
    Retrieve a single address ensuring strict ownership (must belong to caller).
    """
    stmt = select(Address).where(Address.id == address_id, Address.user_id == user_id)
    address = db.scalar(stmt)
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Address with id {address_id} not found in your address book.",
        )
    return address


def create_address(
    db: Session,
    user_id: int,
    address_in: AddressCreate,
) -> Address:
    """
    Create a new delivery destination:
    1. If this is the user's first address, automatically mark it as default.
    2. If is_default=True, unsets default on all existing addresses for this user.
    3. Persists and returns the new Address.
    """
    existing_count_stmt = select(Address.id).where(Address.user_id == user_id).limit(1)
    has_existing = db.scalar(existing_count_stmt) is not None

    is_default = address_in.is_default or not has_existing

    # If this address is set as default, unset default on all other addresses
    if is_default:
        db.execute(
            update(Address)
            .where(Address.user_id == user_id)
            .values(is_default=False)
        )

    db_address = Address(
        user_id=user_id,
        full_name=address_in.full_name,
        phone=address_in.phone,
        street=address_in.street,
        city=address_in.city,
        state=address_in.state,
        postal_code=address_in.postal_code,
        country=address_in.country,
        is_default=is_default,
    )
    db.add(db_address)
    db.commit()
    db.refresh(db_address)

    return db_address


def update_address(
    db: Session,
    address_id: int,
    user_id: int,
    address_update: AddressUpdate,
) -> Address:
    """
    Update an address ensuring ownership.
    If is_default is changed to True, unsets default on all other user addresses.
    """
    address = get_address_by_id(db, address_id=address_id, user_id=user_id)

    if address_update.is_default is True:
        db.execute(
            update(Address)
            .where(Address.user_id == user_id, Address.id != address_id)
            .values(is_default=False)
        )

    update_data = address_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(address, field, value)

    db.commit()
    db.refresh(address)

    return address


def delete_address(db: Session, address_id: int, user_id: int) -> None:
    """
    Delete an address ensuring ownership:
    If the deleted address was default, promote the newest remaining address to default.
    """
    address = get_address_by_id(db, address_id=address_id, user_id=user_id)
    was_default = address.is_default

    db.delete(address)
    db.commit()

    # If we deleted the default address, promote the most recent remaining one
    if was_default:
        new_default = db.scalar(
            select(Address)
            .where(Address.user_id == user_id)
            .order_by(Address.id.desc())
            .limit(1)
        )
        if new_default:
            new_default.is_default = True
            db.commit()
