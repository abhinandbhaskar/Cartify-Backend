from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.auth import require_shop_owner
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductPaginationResponse,
    ProductResponse,
    ProductUpdate,
)
from app.services import product_service

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "/",
    response_model=ProductPaginationResponse,
    summary="List products with search, filters, and pagination",
)
def list_products(
    search: str | None = Query(None, description="Search term matching product name or description"),
    category_id: int | None = Query(None, gt=0, description="Filter products by category ID"),
    min_price: Decimal | None = Query(None, ge=Decimal("0.00"), description="Filter by minimum price"),
    max_price: Decimal | None = Query(None, ge=Decimal("0.00"), description="Filter by maximum price"),
    is_active: bool | None = Query(True, description="Filter active products (pass null for all)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    size: int = Query(10, ge=1, le=100, description="Items per page (max 100)"),
    db: Session = Depends(get_db),
) -> ProductPaginationResponse:
    """
    Retrieve paginated product catalog with dynamic filtering and search (public endpoint).
    """
    items, total, pages = product_service.list_products(
        db=db,
        search=search,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        is_active=is_active,
        page=page,
        size=size,
    )
    return ProductPaginationResponse(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Get product by ID",
)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
) -> ProductResponse:
    """Retrieve full product details including nested category (public endpoint)."""
    product = product_service.get_product_by_id(db=db, product_id=product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found",
        )
    return product


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
)
def create_product(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_shop_owner),
) -> ProductResponse:
    """
    Create a new product in the catalog.
    Requires Shop Owner or Admin role.
    """
    return product_service.create_product(db=db, product_in=product_in)


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Update an existing product",
)
def update_product(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_shop_owner),
) -> ProductResponse:
    """
    Update product details (partial updates allowed).
    Requires Shop Owner or Admin role.
    """
    db_product = product_service.get_product_by_id(db=db, product_id=product_id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found",
        )
    return product_service.update_product(
        db=db, db_product=db_product, update_in=product_update
    )


@router.delete(
    "/{product_id}",
    summary="Delete a product",
)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_shop_owner),
) -> dict[str, str]:
    """
    Delete a product from the catalog.
    Fails with 400 Bad Request if the product has order history (deactivate instead).
    Requires Shop Owner or Admin role.
    """
    db_product = product_service.get_product_by_id(db=db, product_id=product_id)
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {product_id} not found",
        )
    product_service.delete_product(db=db, db_product=db_product)
    return {"message": f"Product '{db_product.name}' deleted successfully"}
