import uuid
from datetime import date, time

from sqlalchemy import Row, delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Doctor, DoctorBlockedDate, DoctorSchedule, DoctorScheduleConfig, Review


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _with_review_count():
    return (
        select(Doctor, func.count(Review.id).label("review_count"))
        .outerjoin(Review, Review.doctor_id == Doctor.id)
        .group_by(Doctor.id)
    )


async def list_doctors(
    db: AsyncSession, q: str | None, specialization: str | None, active_only: bool
) -> list[tuple[Doctor, int]]:
    stmt = _with_review_count().order_by(Doctor.full_name)
    if active_only:
        stmt = stmt.where(Doctor.is_active.is_(True))
    if specialization:
        stmt = stmt.where(Doctor.specialization == specialization)
    if q:
        pattern = f"%{_escape_like(q.strip())}%"
        stmt = stmt.where(
            Doctor.full_name.ilike(pattern, escape="\\")
            | Doctor.specialization.ilike(pattern, escape="\\")
            | func.array_to_string(Doctor.sub_specialties, " ").ilike(pattern, escape="\\")
        )
    return [(row[0], row[1]) for row in (await db.execute(stmt)).all()]


async def get_with_count(db: AsyncSession, doctor_id: uuid.UUID) -> tuple[Doctor, int] | None:
    row = (await db.execute(_with_review_count().where(Doctor.id == doctor_id))).first()
    return (row[0], row[1]) if row else None


async def list_specializations(db: AsyncSession) -> list[str]:
    result = await db.execute(
        select(Doctor.specialization).where(Doctor.is_active.is_(True)).distinct().order_by(Doctor.specialization)
    )
    return list(result.scalars())


async def list_reviews(db: AsyncSession, doctor_id: uuid.UUID) -> list[Review]:
    result = await db.execute(
        select(Review).where(Review.doctor_id == doctor_id).order_by(Review.created_at.desc())
    )
    return list(result.scalars())


# ---------- schedule ----------


async def get_config(db: AsyncSession, doctor_id: uuid.UUID) -> DoctorScheduleConfig | None:
    return await db.get(DoctorScheduleConfig, doctor_id)


async def list_blocked_dates(db: AsyncSession, doctor_id: uuid.UUID) -> list[date]:
    result = await db.execute(
        select(DoctorBlockedDate.blocked_date)
        .where(DoctorBlockedDate.doctor_id == doctor_id)
        .order_by(DoctorBlockedDate.blocked_date)
    )
    return list(result.scalars())


#: Everything needed to render one doctor-day in a single round trip. One row per slot;
#: a single row with NULL slot_time means the doctor has no slots that weekday.
#: Empty result = unknown or inactive doctor.
_DAY_VIEW = text(
    """
    SELECT d.full_name AS doctor_name,
           COALESCE(c.slot_minutes, 30) AS slot_minutes,
           ds.slot_time,
           ds.is_available,
           EXISTS (SELECT 1 FROM doctor_blocked_dates b
                   WHERE b.doctor_id = d.id AND b.blocked_date = :day) AS blocked,
           EXISTS (SELECT 1 FROM appointments a
                   WHERE a.doctor_id = d.id AND a.appointment_date = :day
                     AND a.start_time = ds.slot_time AND a.status <> 'CANCELLED') AS booked
    FROM doctors d
    LEFT JOIN doctor_schedule_configs c ON c.doctor_id = d.id
    LEFT JOIN doctor_schedules ds
           ON ds.doctor_id = d.id AND ds.day_of_week = CAST(:dow AS smallint)
    WHERE d.id = :doctor_id AND d.is_active
    ORDER BY ds.slot_time
    """
)


async def day_view(db: AsyncSession, doctor_id: uuid.UUID, day: date, day_of_week: int) -> list[Row]:
    result = await db.execute(_DAY_VIEW, {"doctor_id": doctor_id, "day": day, "dow": day_of_week})
    return list(result.all())


async def replace_slot_rows(
    db: AsyncSession, doctor_id: uuid.UUID, slots: list[tuple[int, time, bool]]
) -> None:
    await db.execute(delete(DoctorSchedule).where(DoctorSchedule.doctor_id == doctor_id))
    db.add_all(
        DoctorSchedule(doctor_id=doctor_id, day_of_week=dow, slot_time=t, is_available=available)
        for dow, t, available in slots
    )


async def replace_blocked_dates(db: AsyncSession, doctor_id: uuid.UUID, days: list[date]) -> None:
    await db.execute(delete(DoctorBlockedDate).where(DoctorBlockedDate.doctor_id == doctor_id))
    db.add_all(DoctorBlockedDate(doctor_id=doctor_id, blocked_date=d) for d in sorted(set(days)))
