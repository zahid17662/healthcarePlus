import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..errors import not_found
from ..mappers import doctor_out, review_out
from ..repositories import doctors as doctors_repo
from ..schemas import DayAvailabilityOut, DoctorOut, RecommendationOut, ReviewOut
from ..security import get_current_user
from ..services import scheduling

router = APIRouter(tags=["Doctors"], dependencies=[Depends(get_current_user)])


@router.get("/doctors", response_model=list[DoctorOut])
async def list_doctors(
    q: str | None = Query(default=None, max_length=80),
    specialization: str | None = Query(default=None, max_length=80),
    db: AsyncSession = Depends(get_db),
) -> list[DoctorOut]:
    rows = await doctors_repo.list_doctors(db, q, specialization, active_only=True)
    return [doctor_out(d, n) for d, n in rows]


# Declared before /doctors/{doctor_id} so "specializations" isn't parsed as an id.
@router.get("/doctors/specializations", response_model=list[str])
async def list_specializations(db: AsyncSession = Depends(get_db)) -> list[str]:
    return await doctors_repo.list_specializations(db)


@router.get("/doctors/{doctor_id}", response_model=DoctorOut)
async def get_doctor(doctor_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> DoctorOut:
    found = await doctors_repo.get_with_count(db, doctor_id)
    if found is None or not found[0].is_active:
        raise not_found("Doctor")
    return doctor_out(*found)


@router.get("/doctors/{doctor_id}/reviews", response_model=list[ReviewOut])
async def doctor_reviews(doctor_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[ReviewOut]:
    return [review_out(r) for r in await doctors_repo.list_reviews(db, doctor_id)]


@router.get("/doctors/{doctor_id}/slots", response_model=DayAvailabilityOut)
async def doctor_slots(
    doctor_id: uuid.UUID, day: date = Query(alias="date"), db: AsyncSession = Depends(get_db)
) -> DayAvailabilityOut:
    return await scheduling.day_availability(db, doctor_id, day)


@router.get("/recommendations", response_model=list[RecommendationOut], tags=["Recommendations"])
async def recommendations(
    doctor_id: uuid.UUID = Query(alias="doctorId"),
    day: date = Query(alias="date"),
    db: AsyncSession = Depends(get_db),
) -> list[RecommendationOut]:
    return await scheduling.recommend(db, doctor_id, day)
