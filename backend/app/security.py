import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_db
from .errors import AppError
from .models import User, UserRole

JWT_ISSUER = "medibook-api"
JWT_AUDIENCE = "medibook-web"
MAX_PASSWORD_BYTES = 72  # bcrypt's hard input limit

_bearer = HTTPBearer(auto_error=False)
# Compared against when the email is unknown so response time doesn't reveal valid accounts.
_DUMMY_HASH = bcrypt.hashpw(b"timing-equaliser", bcrypt.gensalt()).decode()


def _hash_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:MAX_PASSWORD_BYTES], bcrypt.gensalt()).decode()


def _verify_sync(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:MAX_PASSWORD_BYTES], hashed.encode())
    except ValueError:
        return False


async def hash_password(password: str) -> str:
    # bcrypt is deliberately slow CPU work: keep it off the event loop.
    return await asyncio.to_thread(_hash_sync, password)


async def verify_password(password: str, hashed: str | None) -> bool:
    return await asyncio.to_thread(_verify_sync, password, hashed or _DUMMY_HASH) and hashed is not None


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user.id),
        "role": user.role.value,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> uuid.UUID:
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise AppError(401, "Your session has expired. Please sign in again.") from exc


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise AppError(401, "Authentication required.")
    user = await db.get(User, _decode(creds.credentials))
    if user is None:
        raise AppError(401, "Your session has expired. Please sign in again.")
    return user


async def get_current_patient(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.PATIENT:
        raise AppError(403, "Only patients can do this.")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise AppError(403, "Administrator access required.")
    return user
