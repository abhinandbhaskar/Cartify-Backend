import re
import unicodedata
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import ProductCategory
from app.models.product import Product
from app.schemas.category import CategoryCreate, CategoryUpdate


def generate_slug(text: str) -> str:
    """
    Convert arbitrary text into a URL-friendly slug:
    e.g. 'Men's Clothing & Shoes' -> 'mens-clothing-shoes'
    """
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    slug = re.sub(r"[-\s]+", "-", text)
    return slug


def get_category_by_id(db: Session, category_id: int) -> ProductCategory | None:
    """Retrieve a category by primary key ID."""
    stmt = select(ProductCategory).where(ProductCategory.id == category_id)
    return db.scalar(stmt)


def get_category_by_slug(db: Session, slug: str) -> ProductCategory | None:
    """Retrieve a category by unique URL slug."""
    stmt = select(ProductCategory).where(ProductCategory.slug == slug)
    return db.scalar(stmt)


def get_category_by_name(db: Session, name: str) -> ProductCategory | None:
    """Case-insensitive check for category name."""
    stmt = select(ProductCategory).where(func.lower(ProductCategory.name) == func.lower(name))
    return db.scalar(stmt)


def get_all_categories(db: Session) -> list[ProductCategory]:
    """Retrieve all categories sorted alphabetically by name."""
    stmt = select(ProductCategory).order_by(ProductCategory.name.asc())
    return list(db.scalars(stmt).all())


def create_category(db: Session, category_in: CategoryCreate) -> ProductCategory:
    """
    Create a new product category:
    1. Rejects duplicate category names.
    2. Automatically generates a clean, URL-safe slug.
    3. Handles collision resolution if slug exists.
    """
    if get_category_by_name(db, category_in.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category with name '{category_in.name}' already exists.",
        )

    base_slug = generate_slug(category_in.name)
    slug = base_slug
    counter = 1
    while get_category_by_slug(db, slug):
        slug = f"{base_slug}-{counter}"
        counter += 1

    db_category = ProductCategory(
        name=category_in.name,
        slug=slug,
        description=category_in.description,
    )
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def update_category(
    db: Session,
    db_category: ProductCategory,
    category_update: CategoryUpdate,
) -> ProductCategory:
    """
    Update an existing category:
    Re-generates slug if the name changes and checks for duplicates.
    """
    if category_update.name is not None and category_update.name != db_category.name:
        existing = get_category_by_name(db, category_update.name)
        if existing and existing.id != db_category.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with name '{category_update.name}' already exists.",
            )
        base_slug = generate_slug(category_update.name)
        slug = base_slug
        counter = 1
        while True:
            found = get_category_by_slug(db, slug)
            if not found or found.id == db_category.id:
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        db_category.name = category_update.name
        db_category.slug = slug

    if category_update.description is not None:
        db_category.description = category_update.description

    db.commit()
    db.refresh(db_category)
    return db_category


def delete_category(db: Session, db_category: ProductCategory) -> None:
    """
    Delete a category:
    Protects against deleting categories that still have associated products.
    """
    product_count_stmt = select(func.count(Product.id)).where(Product.category_id == db_category.id)
    product_count = db.scalar(product_count_stmt) or 0
    if product_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete category '{db_category.name}' because it contains {product_count} product(s). Please reassign or delete them first.",
        )

    db.delete(db_category)
    db.commit()
