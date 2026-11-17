"""Availability and recommendation logic (read-only)."""
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..errors import not_found
from ..mappers import doctor_out
from ..repositories import appointments as appts_repo
from ..repositories import doctors as doctors_repo
from ..schemas import DayAvailabilityOut, RecommendationOut, TimeSlotOut, hhmm

RECOMMENDATION_LOOKAHEAD_DAYS = 14
MAX_RECOMMENDATIONS = 3


def clinic_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().clinic_timezone))


def add_minutes(start: time, minutes: int) -> time:
    anchor = datetime.combine(date.min, start) + timedelta(minutes=minutes)
    return anchor.time()


def weekday_index(day: date) -> int:
    """0 = Sunday ... 6 = Saturday (matches doctor_schedules.day_of_week)."""
    return day.isoweekday() % 7


async def load_day(db: AsyncSession, doctor_id: uuid.UUID, day: date) -> tuple[str, DayAvailabilityOut]:
    """(doctor name, availability) from a single query. 404 for unknown/inactive doctors."""
    rows = await doctors_repo.day_view(db, doctor_id, day, weekday_index(day))
    if not rows:
        raise not_found("Doctor")
    name = rows[0].doctor_name
    slot_rows = [r for r in rows if r.slot_time is not None]
    if not slot_rows or rows[0].blocked:
        return name, DayAvailabilityOut(doctor_id=doctor_id, date=day, is_working_day=False, slots=[])

    now = clinic_now()
    now_time = now.time().replace(tzinfo=None)
    slots: list[TimeSlotOut] = []
    for row in slot_rows:
        is_past = day < now.date() or (day == now.date() and row.slot_time <= now_time)
        if not row.is_available:
            status = "blocked"
        elif is_past:
            status = "past"
        elif row.booked:
            status = "booked"
        else:
            status = "available"
        slots.append(
            TimeSlotOut(
                start_time=hhmm(row.slot_time),
                end_time=hhmm(add_minutes(row.slot_time, row.slot_minutes)),
                status=status,
            )
        )
    return name, DayAvailabilityOut(doctor_id=doctor_id, date=day, is_working_day=True, slots=slots)


async def day_availability(db: AsyncSession, doctor_id: uuid.UUID, day: date) -> DayAvailabilityOut:
    return (await load_day(db, doctor_id, day))[1]


async def recommend(db: AsyncSession, doctor_id: uuid.UUID, day: date) -> list[RecommendationOut]:
    """Same-specialty alternatives ranked by earliest open slot, then rating."""
    found = await doctors_repo.get_with_count(db, doctor_id)
    if found is None:
        raise not_found("Doctor")
    now = clinic_now()
    earliest = await appts_repo.earliest_open_slots(
        db,
        specialization=found[0].specialization,
        exclude_doctor_id=doctor_id,
        from_date=day,
        today=now.date(),
        now_time=now.time().replace(tzinfo=None),
        horizon_days=RECOMMENDATION_LOOKAHEAD_DAYS,
        max_results=MAX_RECOMMENDATIONS,
    )
    results: list[RecommendationOut] = []
    for alt_id, alt_day, slot in earliest:
        alt = await doctors_repo.get_with_count(db, alt_id)
        if alt is not None:
            results.append(RecommendationOut(doctor=doctor_out(*alt), date=alt_day, start_time=hhmm(slot)))
    return results
