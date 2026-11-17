from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AppError, conflict
from ..models import User, UserRole
from ..repositories import users as users_repo
from ..schemas import AuthSessionOut, LoginRequest, ProfileUpdate, RegisterRequest, UserOut
from ..security import create_access_token, hash_password, verify_password

_BAD_CREDENTIALS = "Incorrect email or password."


def _session(user: User) -> AuthSessionOut:
    return AuthSessionOut(token=create_access_token(user), user=UserOut.model_validate(user, from_attributes=True))


async def register(db: AsyncSession, req: RegisterRequest) -> AuthSessionOut:
    email = req.email.lower()
    if await users_repo.get_by_email(db, email):
        raise conflict("An account with this email already exists.")
    user = User(
        full_name=req.full_name,
        email=email,
        password_hash=await hash_password(req.password),
        role=UserRole.PATIENT,  # self-registration can never create an admin
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:  # two simultaneous sign-ups with the same email
        await db.rollback()
        raise conflict("An account with this email already exists.") from exc
    return _session(user)


async def login(db: AsyncSession, req: LoginRequest) -> AuthSessionOut:
    user = await users_repo.get_by_email(db, req.email)
    valid = await verify_password(req.password, user.password_hash if user else None)
    if user is None or not valid:
        raise AppError(401, _BAD_CREDENTIALS)
    return _session(user)


async def update_profile(db: AsyncSession, user: User, update: ProfileUpdate) -> UserOut:
    changes = update.model_dump(exclude_unset=True)
    for field, value in changes.items():
        if field == "full_name" and value is None:
            continue
        setattr(user, field, value)
    await db.commit()
    return UserOut.model_validate(user, from_attributes=True)
