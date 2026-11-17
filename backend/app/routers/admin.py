import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..mappers import appointment_out
from ..models import AppointmentStatus
from ..repositories import appointments as appts_repo
from ..schemas import AppointmentOut, DailyStatsOut, DoctorIn, DoctorOut, ScheduleIO
from ..security import get_current_admin
from ..services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(get_current_admin)])


@router.get("/appointments", response_model=list[AppointmentOut])
async def list_appointments(
    day: date | None = Query(default=None, alias="date"),
    status: AppointmentStatus | None = None,
    doctor_id: uuid.UUID | None = Query(default=None, alias="doctorId"),
    db: AsyncSession = Depends(get_db),
) -> list[AppointmentOut]:
    return [appointment_out(r) for r in await appts_repo.list_admin(db, day, status, doctor_id)]


@router.get("/doctors", response_model=list[DoctorOut])
async def list_doctors(db: AsyncSession = Depends(get_db)) -> list[DoctorOut]:
    return await admin_service.list_doctors(db)


@router.post("/doctors", response_model=DoctorOut, status_code=201)
async def create_doctor(payload: DoctorIn, db: AsyncSession = Depends(get_db)) -> DoctorOut:
    return await admin_service.create_doctor(db, payload)


@router.put("/doctors/{doctor_id}", response_model=DoctorOut)
async def update_doctor(doctor_id: uuid.UUID, payload: DoctorIn, db: AsyncSession = Depends(get_db)) -> DoctorOut:
    return await admin_service.update_doctor(db, doctor_id, payload)


@router.get("/doctors/{doctor_id}/schedule", response_model=ScheduleIO)
async def get_schedule(doctor_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ScheduleIO:
    return await admin_service.get_schedule(db, doctor_id)


@router.put("/doctors/{doctor_id}/schedule", response_model=ScheduleIO)
async def update_schedule(doctor_id: uuid.UUID, payload: ScheduleIO, db: AsyncSession = Depends(get_db)) -> ScheduleIO:
    return await admin_service.update_schedule(db, doctor_id, payload)


@router.get("/stats/daily", response_model=DailyStatsOut)
async def daily_stats(day: date = Query(alias="date"), db: AsyncSession = Depends(get_db)) -> DailyStatsOut:
    return await admin_service.daily_stats(db, day)
