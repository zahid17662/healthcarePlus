import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Notification, User


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def list_notifications(db: AsyncSession, user_id: uuid.UUID, limit: int = 20) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def mark_notifications_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    unread = await db.execute(
        select(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )
    for note in unread.scalars():
        note.is_read = True
