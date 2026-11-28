from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.auth import require_admin, require_shop_owner
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get(
    "/",
    response_model=list[CategoryResponse],
    summary="List all categories",
)
def list_categories(
    db: Session = Depends(get_db),
) -> list[CategoryResponse]:
    """Retrieve all categories in alphabetical order (public endpoint)."""
    return category_service.get_all_categories(db=db)


@router.get(
    "/slug/{slug}",
    response_model=CategoryResponse,
    summary="Get category by URL slug",
)
def get_category_by_slug(
    slug: str,
    db: Session = Depends(get_db),
) -> CategoryResponse:
    """Retrieve a category by its unique URL slug (public endpoint)."""
    category = category_service.get_category_by_slug(db=db, slug=slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with slug '{slug}' not found",
        )
    return category


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Get category by ID",
)
def get_category_by_id(
    category_id: int,
    db: Session = Depends(get_db),
) -> CategoryResponse:
    """Retrieve a category by primary key ID (public endpoint)."""
    category = category_service.get_category_by_id(db=db, category_id=category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found",
        )
    return category


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new category",
)
def create_category(
    category_in: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_shop_owner),
) -> CategoryResponse:
    """
    Create a new product category (auto-generates URL slug).
    Requires Shop Owner or Admin role.
    """
    return category_service.create_category(db=db, category_in=category_in)


@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update an existing category",
)
def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_shop_owner),
) -> CategoryResponse:
    """
    Update category name or description (re-generates slug on rename).
    Requires Shop Owner or Admin role.
    """
    db_category = category_service.get_category_by_id(db=db, category_id=category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found",
        )
    return category_service.update_category(
        db=db, db_category=db_category, category_update=category_update
    )


@router.delete(
    "/{category_id}",
    summary="Delete a category",
)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict[str, str]:
    """
    Delete a category.
    Fails with 400 Bad Request if the category still contains products.
    Requires Admin role.
    """
    db_category = category_service.get_category_by_id(db=db, category_id=category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} not found",
        )
    category_service.delete_category(db=db, db_category=db_category)
    return {"message": f"Category '{db_category.name}' deleted successfully"}
