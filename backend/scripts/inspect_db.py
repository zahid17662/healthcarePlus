"""Read-only look at the target database before we change anything."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from app.config import get_settings  # noqa: E402


async def main() -> None:
    s = get_settings()
    dsn = s.async_database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn, ssl="require" if s.requires_ssl else None)
    try:
        print("server:", (await conn.fetchval("select version()"))[:60])
        tables = await conn.fetch(
            "select table_name from information_schema.tables where table_schema='public' order by 1"
        )
        print("public tables:", [t["table_name"] for t in tables] or "none (empty database)")
        enums = await conn.fetch("select typname from pg_type where typtype='e'")
        print("enum types:", [e["typname"] for e in enums] or "none")
    finally:
        await conn.close()


asyncio.run(main())
