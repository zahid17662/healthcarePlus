"""Booking and appointment lifecycle."""
import uuid
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from ..config import get_settings
from ..errors import AppError, conflict, not_found, unprocessable
from ..mappers import appointment_out
from ..models import Appointment, AppointmentStatus, Notification, User, UserRole
from ..repositories import appointments as appts_repo
from ..schemas import AppointmentOut, BookingRequest, hhmm, parse_hhmm
from .scheduling import clinic_now, load_day

SLOT_INDEX_NAME = "idx_unique_active_doctor_slot"
SLOT_TAKEN_MESSAGE = (
    "This time slot was just booked. Please select another slot or view recommended doctors."
)

#: Allowed lifecycle moves: Pending -> Confirmed -> Completed, and cancellation before completion.
STATUS_TRANSITIONS: dict[AppointmentStatus, set[AppointmentStatus]] = {
    AppointmentStatus.PENDING: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED},
    AppointmentStatus.CONFIRMED: {AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED},
    AppointmentStatus.COMPLETED: set(),
    AppointmentStatus.CANCELLED: set(),
}


def _is_slot_conflict(exc: IntegrityError) -> bool:
    return SLOT_INDEX_NAME in str(exc.orig)


async def _load(db: AsyncSession, appointment_id: uuid.UUID) -> AppointmentOut:
    row = await appts_repo.get_row(db, appointment_id)
    if row is None:
        raise not_found("Appointment")
    return appointment_out(row)


async def book(db: AsyncSession, patient: User, req: BookingRequest) -> AppointmentOut:
    today = clinic_now().date()
    if req.date < today:
        raise unprocessable("Choose a date in the future.")
    if req.date > today + timedelta(days=get_settings().booking_window_days):
        raise unprocessable("That date is too far ahead to book.")

    # Friendly validation + fast-path rejection. The unique index below is the real guard.
    doctor_name, day = await load_day(db, req.doctor_id, req.date)
    slot = next((s for s in day.slots if s.start_time == req.start_time), None)
    if slot is None or slot.status in ("blocked", "past"):
        raise unprocessable("This time slot is not available.")
    if slot.status == "booked":
        raise conflict(SLOT_TAKEN_MESSAGE)

    start = parse_hhmm(req.start_time)
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=req.doctor_id,
        appointment_date=req.date,
        start_time=start,
        end_time=parse_hhmm(slot.end_time),
        patient_concerns=req.concerns.strip(),
        symptoms=req.symptoms,
        status=AppointmentStatus.CONFIRMED,
    )
    db.add(appointment)
    db.add(
        Notification(
            user_id=patient.id,
            title="Appointment confirmed",
            message=f"Your visit with {doctor_name} on {req.date.isoformat()} at {hhmm(start)} is locked in.",
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _is_slot_conflict(exc):
            raise conflict(SLOT_TAKEN_MESSAGE) from exc
        raise
    return await _load(db, appointment.id)


async def change_status(
    db: AsyncSession, actor: User, appointment_id: uuid.UUID, new_status: AppointmentStatus
) -> AppointmentOut:
    appt = await appts_repo.get_for_update(db, appointment_id)
    is_patient = actor.role == UserRole.PATIENT
    if appt is None or (is_patient and appt.patient_id != actor.id):
        raise not_found("Appointment")  # same answer for "missing" and "not yours"

    if is_patient:
        if new_status != AppointmentStatus.CANCELLED:
            raise AppError(403, "Patients can only cancel their appointments.")
        if appt.appointment_date < clinic_now().date():
            raise unprocessable("Past appointments cannot be cancelled.")
    if new_status not in STATUS_TRANSITIONS[appt.status]:
        raise conflict(f"Cannot change a {appt.status.value.lower()} appointment to {new_status.value.lower()}.")

    appt.status = new_status
    appt.updated_at = func.now()
    label = new_status.value.lower()
    db.add(
        Notification(
            user_id=appt.patient_id,
            title=f"Appointment {label}",
            message=(
                f"Your appointment on {appt.appointment_date.isoformat()} at {hhmm(appt.start_time)} "
                f"is now {label}."
            ),
        )
    )
    await db.commit()
    return await _load(db, appointment_id)


async def list_mine(db: AsyncSession, patient: User) -> list[AppointmentOut]:
    return [appointment_out(r) for r in await appts_repo.list_for_patient(db, patient.id)]
