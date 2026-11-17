import uuid
from datetime import date, time, timedelta

from sqlalchemy import Row, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Appointment, AppointmentStatus, Doctor, User


def _joined():
    return (
        select(
            Appointment,
            User.full_name.label("patient_name"),
            Doctor.full_name.label("doctor_name"),
            Doctor.specialization.label("specialization"),
        )
        .join(User, User.id == Appointment.patient_id)
        .join(Doctor, Doctor.id == Appointment.doctor_id)
    )


async def get_row(db: AsyncSession, appointment_id: uuid.UUID) -> Row | None:
    return (await db.execute(_joined().where(Appointment.id == appointment_id))).first()


async def get_for_update(db: AsyncSession, appointment_id: uuid.UUID) -> Appointment | None:
    """Row lock so two concurrent status changes can't both pass the transition check."""
    return await db.get(Appointment, appointment_id, with_for_update=True)


async def list_for_patient(db: AsyncSession, patient_id: uuid.UUID) -> list[Row]:
    stmt = (
        _joined()
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc())
    )
    return list((await db.execute(stmt)).all())


async def list_admin(
    db: AsyncSession,
    day: date | None,
    status: AppointmentStatus | None,
    doctor_id: uuid.UUID | None,
    limit: int = 500,
) -> list[Row]:
    stmt = _joined().order_by(Appointment.appointment_date, Appointment.start_time).limit(limit)
    if day:
        stmt = stmt.where(Appointment.appointment_date == day)
    if status:
        stmt = stmt.where(Appointment.status == status)
    if doctor_id:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    return list((await db.execute(stmt)).all())


# ---------- recommendation (bonus) ----------

_EARLIEST_OPEN_SLOT_PER_DOCTOR = text(
    """
    WITH open_slots AS (
        SELECT d.id AS doctor_id,
               CAST(:from_date AS date) + g.n AS day,
               ds.slot_time,
               ROW_NUMBER() OVER (
                   PARTITION BY d.id ORDER BY CAST(:from_date AS date) + g.n, ds.slot_time
               ) AS rn
        FROM doctors d
        CROSS JOIN generate_series(0, CAST(:horizon AS integer)) AS g(n)
        JOIN doctor_schedules ds
          ON ds.doctor_id = d.id
         AND ds.is_available
         AND ds.day_of_week = CAST(EXTRACT(DOW FROM CAST(:from_date AS date) + g.n) AS smallint)
        LEFT JOIN appointments a
          ON a.doctor_id = d.id
         AND a.appointment_date = CAST(:from_date AS date) + g.n
         AND a.start_time = ds.slot_time
         AND a.status <> 'CANCELLED'
        LEFT JOIN doctor_blocked_dates b
          ON b.doctor_id = d.id AND b.blocked_date = CAST(:from_date AS date) + g.n
        WHERE d.specialization = :specialization
          AND d.is_active
          AND d.id <> :exclude_id
          AND a.id IS NULL
          AND b.doctor_id IS NULL
          AND (
                CAST(:from_date AS date) + g.n > CAST(:today AS date)
             OR (CAST(:from_date AS date) + g.n = CAST(:today AS date) AND ds.slot_time > CAST(:now_time AS time))
          )
    )
    SELECT o.doctor_id, o.day, o.slot_time
    FROM open_slots o
    JOIN doctors d ON d.id = o.doctor_id
    WHERE o.rn = 1
    ORDER BY o.day, o.slot_time, d.rating_avg DESC
    LIMIT :max_results
    """
)


async def earliest_open_slots(
    db: AsyncSession,
    specialization: str,
    exclude_doctor_id: uuid.UUID,
    from_date: date,
    today: date,
    now_time: time,
    horizon_days: int,
    max_results: int,
) -> list[tuple[uuid.UUID, date, time]]:
    result = await db.execute(
        _EARLIEST_OPEN_SLOT_PER_DOCTOR,
        {
            "specialization": specialization,
            "exclude_id": exclude_doctor_id,
            "from_date": max(from_date, today),
            "today": today,
            "now_time": now_time,
            "horizon": horizon_days,
            "max_results": max_results,
        },
    )
    return [(r.doctor_id, r.day, r.slot_time) for r in result]


# ---------- admin statistics ----------

_DAY_BREAKDOWN = text(
    """
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE status = 'CONFIRMED') AS confirmed,
           COUNT(*) FILTER (WHERE status = 'PENDING')   AS pending,
           COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed,
           COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled
    FROM appointments
    WHERE appointment_date = :day
    """
)

_SPECIALTY_DEMAND = text(
    """
    SELECT d.specialization, COUNT(*) AS n
    FROM appointments a
    JOIN doctors d ON d.id = a.doctor_id
    WHERE a.appointment_date = :day AND a.status <> 'CANCELLED'
    GROUP BY d.specialization
    ORDER BY n DESC, d.specialization
    """
)

_LAST_7_DAYS = text(
    """
    SELECT appointment_date AS day,
           COUNT(*) AS bookings,
           COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled
    FROM appointments
    WHERE appointment_date BETWEEN :start AND :day
    GROUP BY appointment_date
    """
)

_ACTIVE_DOCTORS = text(
    """
    SELECT COUNT(DISTINCT d.id)
    FROM doctors d
    JOIN doctor_schedules ds
      ON ds.doctor_id = d.id AND ds.is_available AND ds.day_of_week = CAST(:dow AS smallint)
    WHERE d.is_active
      AND NOT EXISTS (
          SELECT 1 FROM doctor_blocked_dates b WHERE b.doctor_id = d.id AND b.blocked_date = :day
      )
    """
)


async def day_breakdown(db: AsyncSession, day: date) -> Row:
    return (await db.execute(_DAY_BREAKDOWN, {"day": day})).one()


async def specialty_demand(db: AsyncSession, day: date) -> list[tuple[str, int]]:
    return [(r.specialization, r.n) for r in await db.execute(_SPECIALTY_DEMAND, {"day": day})]


async def last_seven_days(db: AsyncSession, day: date) -> dict[date, tuple[int, int]]:
    rows = await db.execute(_LAST_7_DAYS, {"start": day - timedelta(days=6), "day": day})
    return {r.day: (r.bookings, r.cancelled) for r in rows}


async def active_doctor_count(db: AsyncSession, day: date) -> int:
    dow = day.isoweekday() % 7
    return int((await db.execute(_ACTIVE_DOCTORS, {"dow": dow, "day": day})).scalar_one())
