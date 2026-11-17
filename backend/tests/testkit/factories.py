"""Test-data builders. Every call inserts uniquely-named rows so tests never collide."""
import uuid
from datetime import date, time, timedelta
from decimal import Decimal

from app.db import SessionFactory
from app.models import (
    Appointment,
    AppointmentStatus,
    Doctor,
    DoctorBlockedDate,
    DoctorSchedule,
    DoctorScheduleConfig,
    Notification,
    Review,
    User,
    UserRole,
)
from app.security import create_access_token, hash_password
from app.services.admin import generate_slots
from app.services.scheduling import add_minutes, clinic_now

TEST_PASSWORD = "Test-Passw0rd!"
ALL_WEEK = (0, 1, 2, 3, 4, 5, 6)

_password_hash: str | None = None


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def future_date(days: int = 3) -> date:
    """A date in the clinic's calendar that is safely in the future (never 'today')."""
    return clinic_now().date() + timedelta(days=days)


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


async def _hash() -> str:
    global _password_hash
    if _password_hash is None:
        _password_hash = await hash_password(TEST_PASSWORD)  # bcrypt once per run, not per user
    return _password_hash


async def make_user(
    role: UserRole = UserRole.PATIENT,
    *,
    full_name: str = "Test Person",
    email: str | None = None,
    phone: str | None = None,
) -> User:
    user = User(
        full_name=full_name,
        email=(email or f"{unique('user')}@example.com").lower(),
        password_hash=await _hash(),
        role=role,
        phone=phone,
    )
    async with SessionFactory() as session:
        session.add(user)
        await session.commit()
    return user


async def make_doctor(
    *,
    name: str | None = None,
    specialization: str = "Cardiology",
    sub_specialties: tuple[str, ...] = ("Echo",),
    working_days: tuple[int, ...] = ALL_WEEK,
    start: time = time(9, 0),
    end: time = time(12, 0),
    slot_minutes: int = 30,
    break_start: time | None = None,
    break_end: time | None = None,
    rating: str = "0.00",
    is_active: bool = True,
    blocked_dates: tuple[date, ...] = (),
    with_schedule: bool = True,
) -> Doctor:
    doctor = Doctor(
        full_name=name or f"Dr. {unique('doc')}",
        specialization=specialization,
        sub_specialties=list(sub_specialties),
        experience_years=7,
        experience_bio="Bio text",
        hourly_rate=Decimal("80.00"),
        avatar_url=None,
        rating_avg=Decimal(rating),
        is_active=is_active,
    )
    async with SessionFactory() as session:
        session.add(doctor)
        await session.flush()
        if with_schedule:
            session.add(
                DoctorScheduleConfig(
                    doctor_id=doctor.id,
                    working_days=sorted(working_days),
                    start_time=start,
                    end_time=end,
                    slot_minutes=slot_minutes,
                    break_start=break_start,
                    break_end=break_end,
                )
            )
            session.add_all(
                DoctorSchedule(doctor_id=doctor.id, day_of_week=dow, slot_time=t, is_available=ok)
                for dow, t, ok in generate_slots(
                    list(working_days), start, end, slot_minutes, break_start, break_end
                )
            )
            session.add_all(DoctorBlockedDate(doctor_id=doctor.id, blocked_date=d) for d in blocked_dates)
        await session.commit()
    return doctor


async def make_review(doctor: Doctor, rating: int, *, patient_name: str = "Reviewer", comment: str = "") -> Review:
    review = Review(doctor_id=doctor.id, patient_name=patient_name, rating=rating, comment=comment)
    async with SessionFactory() as session:
        session.add(review)
        await session.commit()
    return review


async def make_appointment(
    patient: User,
    doctor: Doctor,
    day: date,
    start: time = time(9, 0),
    *,
    status: AppointmentStatus = AppointmentStatus.CONFIRMED,
    concerns: str = "seeded appointment",
    slot_minutes: int = 30,
) -> Appointment:
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=day,
        start_time=start,
        end_time=add_minutes(start, slot_minutes),
        patient_concerns=concerns,
        symptoms=[],
        status=status,
    )
    async with SessionFactory() as session:
        session.add(appt)
        await session.commit()
    return appt


async def make_notification(user: User, title: str = "Hello", *, read: bool = False) -> Notification:
    note = Notification(user_id=user.id, title=title, message="body", is_read=read)
    async with SessionFactory() as session:
        session.add(note)
        await session.commit()
    return note
