import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..mappers import notification_out
from ..models import User
from ..repositories import users as users_repo
from ..schemas import AppointmentOut, BookingRequest, NotificationOut, StatusUpdate
from ..security import get_current_patient, get_current_user
from ..services import booking

router = APIRouter(tags=["Appointments"])


@router.post("/appointments", response_model=AppointmentOut, status_code=201)
async def book_appointment(
    payload: BookingRequest, patient: User = Depends(get_current_patient), db: AsyncSession = Depends(get_db)
) -> AppointmentOut:
    return await booking.book(db, patient, payload)


@router.get("/appointments/me", response_model=list[AppointmentOut])
async def my_appointments(
    patient: User = Depends(get_current_patient), db: AsyncSession = Depends(get_db)
) -> list[AppointmentOut]:
    return await booking.list_mine(db, patient)


@router.patch("/appointments/{appointment_id}/status", response_model=AppointmentOut)
async def update_status(
    appointment_id: uuid.UUID,
    payload: StatusUpdate,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppointmentOut:
    return await booking.change_status(db, actor, appointment_id, payload.status)


@router.get("/notifications", response_model=list[NotificationOut], tags=["Notifications"])
async def list_notifications(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[NotificationOut]:
    return [notification_out(n) for n in await users_repo.list_notifications(db, user.id)]


@router.post("/notifications/read-all", status_code=204, tags=["Notifications"])
async def mark_all_read(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> None:
    await users_repo.mark_notifications_read(db, user.id)
    await db.commit()
