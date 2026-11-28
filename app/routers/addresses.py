from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.address import AddressCreate, AddressResponse, AddressUpdate
from app.services import address_service

router = APIRouter(prefix="/addresses", tags=["Addresses"])


@router.get(
    "/",
    response_model=list[AddressResponse],
    summary="List all addresses for current user",
)
def list_addresses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AddressResponse]:
    """Retrieve all shipping destinations for the authenticated user (default address first)."""
    return address_service.get_user_addresses(db=db, user_id=current_user.id)


@router.get(
    "/{address_id}",
    response_model=AddressResponse,
    summary="Get a specific address by ID",
)
def get_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressResponse:
    """Retrieve an address by ID (enforces ownership)."""
    return address_service.get_address_by_id(
        db=db, address_id=address_id, user_id=current_user.id
    )


@router.post(
    "/",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new address",
)
def create_address(
    address_in: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressResponse:
    """
    Create a new delivery destination:
    - First address created is automatically set as default.
    - Setting is_default=True automatically unsets default on other addresses.
    """
    return address_service.create_address(
        db=db, user_id=current_user.id, address_in=address_in
    )


@router.put(
    "/{address_id}",
    response_model=AddressResponse,
    summary="Update an existing address",
)
def update_address(
    address_id: int,
    address_update: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AddressResponse:
    """Update details or default status of an address (enforces ownership)."""
    return address_service.update_address(
        db=db,
        address_id=address_id,
        user_id=current_user.id,
        address_update=address_update,
    )


@router.delete(
    "/{address_id}",
    summary="Delete an address",
)
def delete_address(
    address_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Delete an address (enforces ownership).
    If the default address is deleted, the newest remaining address becomes default.
    """
    address_service.delete_address(
        db=db, address_id=address_id, user_id=current_user.id
    )
    return {"message": "Address deleted successfully"}
