"""ORM rows -> API schemas (field names differ, so these are explicit)."""
from sqlalchemy import Row

from .models import Doctor, Notification, Review
from .schemas import AppointmentOut, DoctorOut, NotificationOut, ReviewOut, hhmm


def doctor_out(doctor: Doctor, review_count: int) -> DoctorOut:
    return DoctorOut(
        id=doctor.id,
        name=doctor.full_name,
        specialization=doctor.specialization,
        sub_specialties=list(doctor.sub_specialties or []),
        experience_years=doctor.experience_years,
        bio=doctor.experience_bio,
        hourly_rate=float(doctor.hourly_rate),
        image_url=doctor.avatar_url or "",
        average_rating=float(doctor.rating_avg),
        review_count=review_count,
        is_active=doctor.is_active,
    )


def review_out(review: Review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        doctor_id=review.doctor_id,
        patient_name=review.patient_name,
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
    )


def appointment_out(row: Row) -> AppointmentOut:
    appt = row.Appointment
    return AppointmentOut(
        id=appt.id,
        patient_id=appt.patient_id,
        patient_name=row.patient_name,
        doctor_id=appt.doctor_id,
        doctor_name=row.doctor_name,
        specialization=row.specialization,
        date=appt.appointment_date,
        start_time=hhmm(appt.start_time),
        end_time=hhmm(appt.end_time),
        concerns=appt.patient_concerns or "",
        status=appt.status,
        created_at=appt.created_at,
        updated_at=appt.updated_at,
    )


def notification_out(note: Notification) -> NotificationOut:
    return NotificationOut(
        id=note.id,
        user_id=note.user_id,
        title=note.title,
        message=note.message,
        read=note.is_read,
        created_at=note.created_at,
    )
