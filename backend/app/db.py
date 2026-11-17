from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

_settings = get_settings()

_connect_args: dict[str, object] = {}
if _settings.uses_connection_pooler:
    # PgBouncer (transaction mode) cannot reuse server-side prepared statements, so the
    # statement caches must be off. That costs extra round trips per query: for a small
    # API pool prefer the direct (non "-pooler") endpoint, which keeps the caches on.
    _connect_args.update(statement_cache_size=0, prepared_statement_cache_size=0)
if _settings.requires_ssl:
    _connect_args["ssl"] = "require"

engine = create_async_engine(
    _settings.async_database_url,
    # No per-checkout ping (one extra round trip per request). Instead connections are retired
    # before Neon's 5-minute idle suspend could silently drop them.
    pool_recycle=240,
    pool_size=5,
    max_overflow=5,
    connect_args=_connect_args,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """One session per request; the service layer decides when to commit."""
    async with SessionFactory() as session:
        yield session
