from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import User
from ..ratelimit import auth_limiter
from ..schemas import AuthSessionOut, LoginRequest, ProfileUpdate, RegisterRequest, UserOut
from ..security import get_current_user
from ..services import auth as auth_service

router = APIRouter(tags=["Auth"])


@router.post("/auth/register", response_model=AuthSessionOut, status_code=201, dependencies=[Depends(auth_limiter)])
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> AuthSessionOut:
    return await auth_service.register(db, payload)


@router.post("/auth/login", response_model=AuthSessionOut, dependencies=[Depends(auth_limiter)])
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> AuthSessionOut:
    return await auth_service.login(db, payload)


@router.get("/auth/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)


@router.patch("/users/me", response_model=UserOut)
async def update_me(
    payload: ProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UserOut:
    return await auth_service.update_profile(db, user, payload)
