"""Integration fixtures: isolated schema, in-process API client, ready-made users."""
import os
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from testkit import factories

from app.models import User, UserRole

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCHEMA = os.environ["DB_SCHEMA"]  # validated in tests/conftest.py
ALL_TABLES = (
    "notifications",
    "reviews",
    "appointments",
    "doctor_blocked_dates",
    "doctor_schedules",
    "doctor_schedule_configs",
    "doctors",
    "users",
)


def _raw_dsn() -> tuple[str, str | None]:
    from app.config import get_settings

    settings = get_settings()
    dsn = settings.async_database_url.replace("postgresql+asyncpg://", "postgresql://")
    return dsn, "require" if settings.requires_ssl else None


@pytest_asyncio.fixture(scope="session", autouse=True)
async def isolated_schema() -> AsyncIterator[None]:
    """(Re)create the test schema, prove the app is pinned to it, drop it when finished."""
    if os.environ.get("TEST_HAS_REAL_DATABASE") != "1":
        pytest.skip("No database configured: set TEST_DATABASE_URL or DATABASE_URL in backend/.env")

    from app.config import get_settings
    from app.db import engine

    assert get_settings().db_schema == SCHEMA, "app is not configured for the test schema"
    dsn, ssl = _raw_dsn()

    conn = await asyncpg.connect(dsn, ssl=ssl)
    try:
        # SCHEMA is validated against a strict pattern and forbidden-name list in tests/conftest.py.
        await conn.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
        await conn.execute(f'CREATE SCHEMA "{SCHEMA}"')
        await conn.execute(f'SET search_path TO "{SCHEMA}"')
        for sql_file in sorted((BACKEND_DIR / "sql").glob("*.sql")):
            await conn.execute(sql_file.read_text(encoding="utf-8"))
    finally:
        await conn.close()

    # Hard stop unless the application's OWN engine resolves to the test schema.
    async with engine.connect() as probe:
        current = (await probe.execute(text("select current_schema()"))).scalar_one()
        # The schema that actually owns the table an unqualified `users` resolves to.
        users_schema = (
            await probe.execute(
                text(
                    "select n.nspname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                    "where c.oid = to_regclass('users')"
                )
            )
        ).scalar_one_or_none()
    if current != SCHEMA or users_schema != SCHEMA:
        pytest.exit(
            f"ABORT: app engine is on schema {current!r} (users -> {users_schema!r}), expected {SCHEMA!r}. "
            "Refusing to run tests against anything but the isolated test schema.",
            returncode=3,
        )

    yield

    await engine.dispose()
    conn = await asyncpg.connect(dsn, ssl=ssl)
    try:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> None:
    from app.ratelimit import auth_limiter

    auth_limiter.reset()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def client_no_raise() -> AsyncIterator[AsyncClient]:
    """Like `client`, but unhandled server errors come back as HTTP 500 instead of raising."""
    from app.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncSession]:
    from app.db import SessionFactory

    async with SessionFactory() as session:
        yield session


@pytest_asyncio.fixture
async def clean_db() -> None:
    """Empty every table (test schema only) for tests that assert on global counts."""
    from app.db import SessionFactory

    async with SessionFactory() as session:
        qualified = ", ".join(f'"{SCHEMA}".{t}' for t in ALL_TABLES)
        await session.execute(text(f"TRUNCATE {qualified} RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest_asyncio.fixture
async def patient() -> User:
    return await factories.make_user(UserRole.PATIENT, full_name="Pat Patient")


@pytest_asyncio.fixture
async def other_patient() -> User:
    return await factories.make_user(UserRole.PATIENT, full_name="Olive Other")


@pytest_asyncio.fixture
async def admin() -> User:
    return await factories.make_user(UserRole.ADMIN, full_name="Ada Admin")


@pytest.fixture
def as_patient(patient: User) -> dict[str, str]:
    return factories.auth_header(patient)


@pytest.fixture
def as_other_patient(other_patient: User) -> dict[str, str]:
    return factories.auth_header(other_patient)


@pytest.fixture
def as_admin(admin: User) -> dict[str, str]:
    return factories.auth_header(admin)
