"""Password hashing, JWT creation/validation and the role guards (no database needed)."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import get_settings
from app.errors import AppError
from app.models import User, UserRole
from app.security import (
    JWT_AUDIENCE,
    JWT_ISSUER,
    _decode,
    create_access_token,
    get_current_admin,
    get_current_patient,
    hash_password,
    verify_password,
)


def make_user(role: UserRole = UserRole.PATIENT) -> User:
    return User(id=uuid.uuid4(), full_name="T", email="t@example.com", password_hash="x", role=role)


def forge(
    *,
    sub: str | None = None,
    key: str | None = None,
    algorithm: str = "HS256",
    audience: str = JWT_AUDIENCE,
    issuer: str = JWT_ISSUER,
    expires_in: float = 3600,
    drop: tuple[str, ...] = (),
) -> str:
    now = datetime.now(timezone.utc)
    claims: dict[str, object] = {
        "sub": sub or str(uuid.uuid4()),
        "aud": audience,
        "iss": issuer,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    for name in drop:
        claims.pop(name)
    return jwt.encode(claims, key if key is not None else get_settings().jwt_secret, algorithm=algorithm)


class TestPasswordHashing:
    async def test_correct_password_verifies(self) -> None:
        hashed = await hash_password("Correct-Horse-1")
        assert await verify_password("Correct-Horse-1", hashed) is True

    async def test_wrong_password_is_rejected(self) -> None:
        hashed = await hash_password("Correct-Horse-1")
        assert await verify_password("Wrong-Horse-1", hashed) is False

    async def test_hash_is_salted_and_never_the_plain_password(self) -> None:
        first, second = await hash_password("Same-Password-1"), await hash_password("Same-Password-1")
        assert first != second
        assert "Same-Password-1" not in first

    async def test_unknown_account_never_verifies(self) -> None:
        """Login passes None for a missing user; it must fail (and still do a dummy compare)."""
        assert await verify_password("anything", None) is False

    async def test_malformed_stored_hash_is_rejected_not_raised(self) -> None:
        assert await verify_password("anything", "not-a-bcrypt-hash") is False


class TestAccessToken:
    def test_round_trips_the_user_id(self) -> None:
        user = make_user()
        assert _decode(create_access_token(user)) == user.id

    def test_carries_the_expected_claims(self) -> None:
        user = make_user(UserRole.ADMIN)
        claims = jwt.decode(
            create_access_token(user),
            get_settings().jwt_secret,
            algorithms=["HS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        assert claims["sub"] == str(user.id)
        assert claims["role"] == "ADMIN"
        assert claims["exp"] > claims["iat"]

    def test_lifetime_follows_the_configured_expiry(self) -> None:
        claims = jwt.decode(create_access_token(make_user()), options={"verify_signature": False})
        lifetime = claims["exp"] - claims["iat"]
        assert lifetime == get_settings().jwt_expire_minutes * 60


class TestTokenRejection:
    @pytest.mark.parametrize(
        "token",
        [
            pytest.param(lambda: forge(expires_in=-10), id="expired"),
            pytest.param(lambda: forge(key="a-different-secret-" + "x" * 30), id="wrong-signature"),
            pytest.param(lambda: forge(audience="someone-else"), id="wrong-audience"),
            pytest.param(lambda: forge(issuer="someone-else"), id="wrong-issuer"),
            pytest.param(lambda: forge(drop=("exp",)), id="missing-exp"),
            pytest.param(lambda: forge(drop=("sub",)), id="missing-sub"),
            pytest.param(lambda: forge(sub="not-a-uuid"), id="non-uuid-subject"),
            pytest.param(lambda: jwt.encode({"sub": str(uuid.uuid4())}, "", algorithm="none"), id="alg-none"),
            pytest.param(lambda: "garbage", id="garbage"),
            pytest.param(lambda: "", id="empty"),
        ],
    )
    def test_invalid_tokens_are_401(self, token) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(AppError) as exc:
            _decode(token())
        assert exc.value.status_code == 401


class TestRoleGuards:
    async def test_patient_guard_accepts_a_patient(self) -> None:
        user = make_user(UserRole.PATIENT)
        assert await get_current_patient(user) is user

    async def test_patient_guard_rejects_an_admin_with_403(self) -> None:
        with pytest.raises(AppError) as exc:
            await get_current_patient(make_user(UserRole.ADMIN))
        assert exc.value.status_code == 403

    async def test_admin_guard_accepts_an_admin(self) -> None:
        user = make_user(UserRole.ADMIN)
        assert await get_current_admin(user) is user

    async def test_admin_guard_rejects_a_patient_with_403(self) -> None:
        with pytest.raises(AppError) as exc:
            await get_current_admin(make_user(UserRole.PATIENT))
        assert exc.value.status_code == 403
