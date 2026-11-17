from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# libpq-only query params that asyncpg rejects.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_expire_minutes: int = 720
    jwt_algorithm: str = "HS256"
    cors_origins: str = "http://localhost:5173"
    # Slot "past/today" decisions use the clinic's local time, not the server's.
    clinic_timezone: str = "Asia/Dhaka"
    booking_window_days: int = 60

    @field_validator("jwt_secret")
    @classmethod
    def _secret_long_enough(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    @property
    def async_database_url(self) -> str:
        """SQLAlchemy asyncpg URL with libpq-only params removed."""
        parts = urlsplit(self.database_url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if k not in _LIBPQ_ONLY_PARAMS]
        return urlunsplit(
            ("postgresql+asyncpg", parts.netloc, parts.path, urlencode(query), "")
        )

    @property
    def requires_ssl(self) -> bool:
        return "sslmode=require" in self.database_url or "neon.tech" in self.database_url

    @property
    def uses_connection_pooler(self) -> bool:
        host = urlsplit(self.database_url).hostname or ""
        return "-pooler" in host or "pgbouncer" in self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
