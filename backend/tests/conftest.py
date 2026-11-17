"""Test-session bootstrap.

SAFETY MODEL: the suite must never read or write production data.
  * Every connection the app makes during tests is pinned to the Postgres schema TEST_SCHEMA
    (via the DB_SCHEMA setting -> `SET search_path` on every new connection), never `public`.
  * `tests/integration/conftest.py` recreates that schema from sql/*.sql for each run, verifies
    through the app's own engine that `current_schema()` really is TEST_SCHEMA, and aborts the
    whole session if not. The schema is dropped again at the end.

Database URL, in priority order: TEST_DATABASE_URL, then DATABASE_URL from backend/.env.
Use a *direct* Postgres endpoint (not a PgBouncer "-pooler" host): a session-level SET is unreliable
behind a transaction pooler. CI can point TEST_DATABASE_URL at a throw-away Postgres service.
"""
import os
import re
from pathlib import Path

import pytest
from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[1]

TEST_SCHEMA = os.environ.get("TEST_DB_SCHEMA", "medibook_test")
_FORBIDDEN_SCHEMAS = {"public", "pg_catalog", "information_schema", "pg_toast"}
if (
    not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", TEST_SCHEMA)
    or TEST_SCHEMA in _FORBIDDEN_SCHEMAS
    or not TEST_SCHEMA.startswith(("test", "medibook_test"))
):
    raise RuntimeError(
        f"Refusing to run: TEST_DB_SCHEMA={TEST_SCHEMA!r} must start with 'test' or "
        "'medibook_test' and must not be a system or production schema."
    )

# Placeholder lets the DB-free unit tests run where no database is configured (e.g. a bare CI job).
_PLACEHOLDER_URL = "postgresql://unit:unit@localhost:5432/unit"


def _resolve_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        return dotenv_values(env_file).get("DATABASE_URL") or _PLACEHOLDER_URL
    return _PLACEHOLDER_URL


# Must happen before anything imports `app` (settings and the engine are built at import time).
os.environ["DATABASE_URL"] = _resolve_database_url()
os.environ["DB_SCHEMA"] = TEST_SCHEMA
os.environ["JWT_SECRET"] = "pytest-only-signing-key-" + "k" * 32
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["CLINIC_TIMEZONE"] = "Asia/Dhaka"

# Integration tests skip themselves (instead of failing) when no real database is configured.
os.environ["TEST_HAS_REAL_DATABASE"] = "1" if os.environ["DATABASE_URL"] != _PLACEHOLDER_URL else "0"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Tag tests by directory so `-m unit` / `-m integration` work without per-test decorators."""
    for item in items:
        path = Path(str(item.fspath))
        if "integration" in path.parts:
            item.add_marker(pytest.mark.integration)
        elif "unit" in path.parts:
            item.add_marker(pytest.mark.unit)
