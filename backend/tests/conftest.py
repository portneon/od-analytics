import os
import uuid

os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://email_intel:email_intel@localhost:5432/email_intel_test")
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["JWT_SECRET"] = "test-secret"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.core.security import hash_password

engine = create_engine(settings.DATABASE_URL, future=True)
TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _truncate_all():
    with engine.begin() as conn:
        table_names = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        conn.exec_driver_sql(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE")


@pytest.fixture
def db_session():
    """Plain session against the real test database. Application code under
    test (services, API routes) calls db.commit() itself, so this can't be a
    nested-transaction/rollback session -- state is reset between tests via
    _truncate_all() instead."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        _truncate_all()


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def tenant(db_session):
    t = Tenant(name="Test Co", slug=f"test-co-{uuid.uuid4().hex[:8]}")
    db_session.add(t)
    db_session.flush()
    return t


@pytest.fixture
def user(db_session, tenant):
    u = User(tenant_id=tenant.id, email="admin@test.com", name="Admin", role=UserRole.ADMIN, password_hash=hash_password("password123"))
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def auth_headers(user):
    from app.core.security import create_access_token

    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}
