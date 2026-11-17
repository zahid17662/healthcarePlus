"""Apply every sql/*.sql file in order, each in one transaction."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncpg  # noqa: E402

from app.config import get_settings  # noqa: E402


async def main() -> None:
    s = get_settings()
    dsn = s.async_database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn, ssl="require" if s.requires_ssl else None)
    try:
        for path in sorted((ROOT / "sql").glob("*.sql")):
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
            print(f"applied {path.name}")
        tables = await conn.fetch(
            "select table_name from information_schema.tables where table_schema='public' order by 1"
        )
        print("tables:", ", ".join(t["table_name"] for t in tables))
    finally:
        await conn.close()


asyncio.run(main())
