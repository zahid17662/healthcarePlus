"""Proof that the suite is sandboxed, plus the always-on infrastructure endpoints."""
import asyncpg
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from testkit import factories

from app.config import get_settings


async def test_app_session_is_pinned_to_the_test_schema(db: AsyncSession) -> None:
    current = (await db.execute(text("select current_schema()"))).scalar_one()
    assert current == get_settings().db_schema == "medibook_test"


async def test_tables_resolve_inside_the_test_schema(db: AsyncSession) -> None:
    owning_schema = (
        await db.execute(
            text(
                "select n.nspname from pg_class c join pg_namespace n on n.oid = c.relnamespace "
                "where c.oid = to_regclass('appointments')"
            )
        )
    ).scalar_one()
    assert owning_schema == "medibook_test"


async def test_rows_created_by_tests_never_reach_the_public_schema() -> None:
    """Looks at the production-facing `public` schema with a separate, unpinned connection."""
    user = await factories.make_user(email=f"{factories.unique('isolation')}@example.com")

    settings = get_settings()
    dsn = settings.async_database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn, ssl="require" if settings.requires_ssl else None)
    try:
        if await conn.fetchval("select to_regclass('public.users')") is None:
            return  # fresh database with no production tables: nothing that could be polluted
        leaked = await conn.fetchval("select count(*) from public.users where email = $1", user.email)
        in_test_schema = await conn.fetchval(
            "select count(*) from medibook_test.users where email = $1", user.email
        )
    finally:
        await conn.close()
    assert leaked == 0
    assert in_test_schema == 1


async def test_health_endpoint_is_public(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_cors_allows_the_configured_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/doctors",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_cors_rejects_an_unknown_origin(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/doctors",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


async def test_cors_does_not_allow_credentials(client: AsyncClient) -> None:
    response = await client.options(
        "/api/v1/doctors",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-credentials" not in response.headers


async def test_validation_errors_are_one_readable_line_and_never_echo_input(client: AsyncClient) -> None:
    secret = "ShortPw"  # 7 chars: fails the 8-char minimum
    response = await client.post(
        "/api/v1/auth/register",
        json={"fullName": "Valid Name", "email": "valid@example.com", "password": secret},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str) and detail.startswith("password:")
    assert secret not in response.text


async def test_malformed_json_is_a_422_not_a_server_error(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
