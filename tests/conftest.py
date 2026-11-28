from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.address import Address
from app.models.category import ProductCategory
from app.models.product import Product
from app.models.user import User, UserRole

# Isolated in-memory SQLite database for test execution
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Session:
    """Provide a clean database session per test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_admin(db: Session) -> User:
    user = User(
        name="Admin User",
        email="admin@cartify.com",
        password_hash=hash_password("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_shop_owner(db: Session) -> User:
    user = User(
        name="Shop Owner",
        email="merchant@cartify.com",
        password_hash=hash_password("merchantpass123"),
        role=UserRole.SHOP_OWNER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_customer(db: Session) -> User:
    user = User(
        name="John Customer",
        email="customer@cartify.com",
        password_hash=hash_password("customerpass123"),
        role=UserRole.CUSTOMER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_headers(test_admin: User) -> dict[str, str]:
    token = create_access_token(subject=test_admin.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def shop_owner_headers(test_shop_owner: User) -> dict[str, str]:
    token = create_access_token(subject=test_shop_owner.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def customer_headers(test_customer: User) -> dict[str, str]:
    token = create_access_token(subject=test_customer.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_category(db: Session) -> ProductCategory:
    category = ProductCategory(
        name="Electronics",
        slug="electronics",
        description="Gadgets and electronic equipment",
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@pytest.fixture
def test_product(db: Session, test_category: ProductCategory) -> Product:
    product = Product(
        name="Wireless Noise-Canceling Headphones",
        description="High-fidelity audio with 30-hour battery life",
        price=Decimal("199.99"),
        stock=20,
        category_id=test_category.id,
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@pytest.fixture
def test_address(db: Session, test_customer: User) -> Address:
    address = Address(
        user_id=test_customer.id,
        full_name="John Customer",
        phone="+91-9876543210",
        street="123 MG Road, Suite 4B",
        city="Bangalore",
        state="Karnataka",
        postal_code="560001",
        country="India",
        is_default=True,
    )
    db.add(address)
    db.commit()
    db.refresh(address)
    return address
