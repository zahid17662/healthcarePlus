"""Admin-only operations: doctors, schedules, statistics."""
import uuid
from datetime import date, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import not_found, unprocessable
from ..mappers import doctor_out
from ..models import Doctor, DoctorScheduleConfig
from ..repositories import appointments as appts_repo
from ..repositories import doctors as doctors_repo
from ..schemas import (
    DailyStatsOut,
    DayCount,
    DoctorIn,
    DoctorOut,
    ScheduleIO,
    SpecialtyCount,
    hhmm,
    parse_hhmm,
)
from .scheduling import add_minutes

DEFAULT_WORKING_DAYS = [1, 2, 3, 4, 5]


def _apply(doctor: Doctor, data: DoctorIn) -> None:
    doctor.full_name = data.name
    doctor.specialization = data.specialization
    doctor.sub_specialties = [s.strip() for s in data.sub_specialties if s.strip()]
    doctor.experience_years = data.experience_years
    doctor.experience_bio = data.bio
    doctor.hourly_rate = data.hourly_rate  # type: ignore[assignment]
    doctor.avatar_url = data.image_url or None
    doctor.is_active = data.is_active


def generate_slots(
    working_days: list[int], start: time, end: time, slot_minutes: int, break_start: time | None, break_end: time | None
) -> list[tuple[int, time, bool]]:
    """Materialise (weekday, slot start, is_available); slots overlapping the break are unavailable."""
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    times = [
        add_minutes(time(0, 0), m)
        for m in range(start_min, end_min - slot_minutes + 1, slot_minutes)
    ]

    def in_break(t: time) -> bool:
        if break_start is None or break_end is None:
            return False
        return t < break_end and add_minutes(t, slot_minutes) > break_start

    return [(day, t, not in_break(t)) for day in sorted(set(working_days)) for t in times]


async def list_doctors(db: AsyncSession) -> list[DoctorOut]:
    return [doctor_out(d, n) for d, n in await doctors_repo.list_doctors(db, None, None, active_only=False)]


async def create_doctor(db: AsyncSession, data: DoctorIn) -> DoctorOut:
    doctor = Doctor()
    _apply(doctor, data)
    db.add(doctor)
    await db.flush()
    config = DoctorScheduleConfig(
        doctor_id=doctor.id,
        working_days=DEFAULT_WORKING_DAYS,
        start_time=time(9, 0),
        end_time=time(17, 0),
        slot_minutes=30,
        break_start=time(13, 0),
        break_end=time(14, 0),
    )
    db.add(config)
    await doctors_repo.replace_slot_rows(
        db, doctor.id, generate_slots(DEFAULT_WORKING_DAYS, time(9, 0), time(17, 0), 30, time(13, 0), time(14, 0))
    )
    await db.commit()
    return doctor_out(doctor, 0)


async def update_doctor(db: AsyncSession, doctor_id: uuid.UUID, data: DoctorIn) -> DoctorOut:
    found = await doctors_repo.get_with_count(db, doctor_id)
    if found is None:
        raise not_found("Doctor")
    doctor, review_count = found
    _apply(doctor, data)
    await db.commit()
    return doctor_out(doctor, review_count)


async def get_schedule(db: AsyncSession, doctor_id: uuid.UUID) -> ScheduleIO:
    config = await doctors_repo.get_config(db, doctor_id)
    if config is None:
        raise not_found("Schedule")
    return ScheduleIO(
        doctor_id=doctor_id,
        working_days=sorted(config.working_days),
        start_time=hhmm(config.start_time),
        end_time=hhmm(config.end_time),
        slot_minutes=config.slot_minutes,
        break_start=hhmm(config.break_start) if config.break_start else None,
        break_end=hhmm(config.break_end) if config.break_end else None,
        blocked_dates=await doctors_repo.list_blocked_dates(db, doctor_id),
    )


def _validate_schedule(data: ScheduleIO) -> tuple[time, time, time | None, time | None]:
    start, end = parse_hhmm(data.start_time), parse_hhmm(data.end_time)
    if end <= start:
        raise unprocessable("End time must be after start time.")
    if (data.break_start is None) != (data.break_end is None):
        raise unprocessable("Set both break start and break end, or neither.")
    b_start = parse_hhmm(data.break_start) if data.break_start else None
    b_end = parse_hhmm(data.break_end) if data.break_end else None
    if b_start and b_end and b_end <= b_start:
        raise unprocessable("Break end must be after break start.")
    return start, end, b_start, b_end


async def update_schedule(db: AsyncSession, doctor_id: uuid.UUID, data: ScheduleIO) -> ScheduleIO:
    if await doctors_repo.get_with_count(db, doctor_id) is None:
        raise not_found("Doctor")
    start, end, b_start, b_end = _validate_schedule(data)
    days = sorted(set(data.working_days))

    config = await doctors_repo.get_config(db, doctor_id)
    if config is None:
        config = DoctorScheduleConfig(doctor_id=doctor_id)
        db.add(config)
    config.working_days = days
    config.start_time, config.end_time = start, end
    config.slot_minutes = data.slot_minutes
    config.break_start, config.break_end = b_start, b_end

    # Existing bookings are kept as-is; only future slot offers change.
    await doctors_repo.replace_slot_rows(db, doctor_id, generate_slots(days, start, end, data.slot_minutes, b_start, b_end))
    await doctors_repo.replace_blocked_dates(db, doctor_id, data.blocked_dates)
    await db.commit()
    return await get_schedule(db, doctor_id)


async def daily_stats(db: AsyncSession, day: date) -> DailyStatsOut:
    breakdown = await appts_repo.day_breakdown(db, day)
    per_day = await appts_repo.last_seven_days(db, day)
    window = [day - timedelta(days=offset) for offset in range(6, -1, -1)]
    return DailyStatsOut(
        date=day,
        total_bookings=breakdown.total,
        confirmed=breakdown.confirmed,
        pending=breakdown.pending,
        completed=breakdown.completed,
        cancelled=breakdown.cancelled,
        cancellation_rate=(breakdown.cancelled / breakdown.total) if breakdown.total else 0.0,
        active_doctors=await appts_repo.active_doctor_count(db, day),
        by_specialty=[SpecialtyCount(specialization=s, count=n) for s, n in await appts_repo.specialty_demand(db, day)],
        last7_days=[
            DayCount(date=d, bookings=per_day.get(d, (0, 0))[0], cancelled=per_day.get(d, (0, 0))[1]) for d in window
        ],
    )


