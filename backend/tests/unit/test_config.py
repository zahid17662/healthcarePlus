import pytest
from pydantic import ValidationError

from app.config import Settings

NEON_URL = "postgresql://user:pw@ep-demo-pooler.c-2.aws.neon.tech/db?sslmode=require&channel_binding=require"
SECRET = "s" * 40


def make(**overrides: object) -> Settings:
    """Settings isolated from backend/.env and the process environment's DB_* values."""
    values: dict[str, object] = {"database_url": NEON_URL, "jwt_secret": SECRET}
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


class TestAsyncDatabaseUrl:
    def test_switches_to_asyncpg_driver(self) -> None:
        assert make().async_database_url.startswith("postgresql+asyncpg://")

    def test_drops_libpq_only_parameters(self) -> None:
        url = make().async_database_url
        assert "sslmode" not in url
        assert "channel_binding" not in url

    def test_keeps_other_query_parameters(self) -> None:
        url = make(database_url="postgresql://u:p@db.example.com/x?sslmode=require&application_name=medibook")
        assert url.async_database_url.endswith("?application_name=medibook")

    def test_keeps_credentials_host_and_database(self) -> None:
        url = make(database_url="postgresql://u:p@db.example.com:6543/clinic").async_database_url
        assert url == "postgresql+asyncpg://u:p@db.example.com:6543/clinic"


class TestSslDetection:
    @pytest.mark.parametrize(
        "url",
        [
            "postgresql://u:p@db.example.com/x?sslmode=require",
            "postgresql://u:p@ep-1.neon.tech/x",
        ],
        ids=["sslmode-require", "neon-host"],
    )
    def test_ssl_required(self, url: str) -> None:
        assert make(database_url=url).requires_ssl is True

    def test_plain_local_database_does_not_require_ssl(self) -> None:
        assert make(database_url="postgresql://u:p@localhost/x").requires_ssl is False


class TestPoolerDetection:
    def test_pooler_host_detected(self) -> None:
        assert make(database_url=NEON_URL).uses_connection_pooler is True

    def test_direct_host_is_not_pooled(self) -> None:
        assert make(database_url="postgresql://u:p@ep-demo.c-2.aws.neon.tech/db").uses_connection_pooler is False

    def test_pgbouncer_flag_in_url_detected(self) -> None:
        assert make(database_url="postgresql://u:p@db.example.com/x?pgbouncer=true").uses_connection_pooler is True


class TestCorsOrigins:
    def test_splits_and_trims(self) -> None:
        origins = make(cors_origins=" https://a.example , https://b.example ,, ").cors_origin_list
        assert origins == ["https://a.example", "https://b.example"]

    def test_default_is_local_dev_origin(self) -> None:
        assert make().cors_origin_list == ["http://localhost:5173"]


class TestJwtSecret:
    def test_short_secret_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least 32"):
            make(jwt_secret="too-short")

    def test_32_character_secret_accepted(self) -> None:
        assert make(jwt_secret="x" * 32).jwt_secret == "x" * 32


class TestDatabaseSchema:
    """DB_SCHEMA pins every connection's search_path (used by the test suite for isolation)."""

    def test_defaults_to_none_when_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DB_SCHEMA", raising=False)
        assert make().db_schema is None

    def test_accepts_a_plain_identifier(self) -> None:
        assert make(db_schema="medibook_test").db_schema == "medibook_test"

    @pytest.mark.parametrize(
        "bad",
        ["public; DROP TABLE users", "Bad-Name", "has space", "", "1starts_with_digit", "x" * 64],
        ids=["injection", "dash-and-caps", "space", "empty", "leading-digit", "too-long"],
    )
    def test_rejects_unsafe_identifiers(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            make(db_schema=bad)
