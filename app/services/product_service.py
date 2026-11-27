import math
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.category import ProductCategory
from app.models.order import OrderItem
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.category_service import get_category_by_id


def get_product_by_id(db: Session, product_id: int) -> Product | None:
    """
    Retrieve a single product by primary key ID.
    Eagerly loads the associated category relationship via joinedload.
    """
    stmt = (
        select(Product)
        .options(joinedload(Product.category))
        .where(Product.id == product_id)
    )
    return db.scalar(stmt)


def list_products(
    db: Session,
    search: str | None = None,
    category_id: int | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    is_active: bool | None = True,
    page: int = 1,
    size: int = 10,
) -> tuple[list[Product], int, int]:
    """
    Retrieve a paginated list of products with optional search and filters:
    - search: Case-insensitive match on product name or description.
    - category_id: Filter by category foreign key.
    - min_price / max_price: Price range filtering.
    - is_active: Filter by active status (defaults to True for catalog, None shows all).
    - page / size: 1-indexed pagination parameters.

    Returns:
        tuple of (items, total_count, total_pages)
    """
    conditions = []

    # Filter by active status (if None is explicitly passed, show both active & inactive)
    if is_active is not None:
        conditions.append(Product.is_active == is_active)

    # Filter by category
    if category_id is not None:
        conditions.append(Product.category_id == category_id)

    # Filter by price range
    if min_price is not None:
        conditions.append(Product.price >= min_price)
    if max_price is not None:
        conditions.append(Product.price <= max_price)

    # Filter by case-insensitive text search in name or description
    if search:
        search_pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Product.name.ilike(search_pattern),
                Product.description.ilike(search_pattern),
            )
        )

    # 1. Total matching count query
    count_stmt = select(func.count(Product.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = db.scalar(count_stmt) or 0

    # 2. Total pages calculation
    pages = math.ceil(total / size) if total > 0 else 0

    # 3. Paginated items query with eagerly loaded category
    offset = (page - 1) * size
    stmt = (
        select(Product)
        .options(joinedload(Product.category))
    )
    if conditions:
        stmt = stmt.where(*conditions)

    stmt = stmt.order_by(Product.id.desc()).offset(offset).limit(size)
    products = list(db.scalars(stmt).unique().all())

    return products, total, pages


def create_product(db: Session, product_in: ProductCreate) -> Product:
    """
    Create a new product in the database:
    1. Validates that the referenced category_id exists.
    2. Inserts the product and commits.
    3. Returns the persisted product with the category relationship eagerly loaded.
    """
    category = get_category_by_id(db, product_in.category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category with id {product_in.category_id} does not exist.",
        )

    db_product = Product(**product_in.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    # Return with eagerly loaded category relationship
    return get_product_by_id(db, db_product.id)  # type: ignore[return-value]


def update_product(
    db: Session,
    db_product: Product,
    update_in: ProductUpdate,
) -> Product:
    """
    Update an existing product (partial updates supported):
    1. If category_id is updated, validates that the new category exists.
    2. Updates only the fields provided in update_in.
    3. Commits and returns the updated product.
    """
    if update_in.category_id is not None and update_in.category_id != db_product.category_id:
        category = get_category_by_id(db, update_in.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with id {update_in.category_id} does not exist.",
            )

    update_data = update_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_product, field, value)

    db.commit()
    db.refresh(db_product)

    return get_product_by_id(db, db_product.id)  # type: ignore[return-value]


def delete_product(db: Session, db_product: Product) -> None:
    """
    Delete a product:
    Guards against deleting products referenced in order history.
    If orders exist, client must deactivate (is_active=False) instead.
    """
    order_item_check = select(OrderItem.id).where(OrderItem.product_id == db_product.id).limit(1)
    if db.scalar(order_item_check):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot delete product '{db_product.name}' because it is part of existing customer orders. "
                "Deactivate it instead by setting is_active=False."
            ),
        )

    db.delete(db_product)
    db.commit()
