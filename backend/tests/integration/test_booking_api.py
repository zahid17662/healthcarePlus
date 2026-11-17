"""Booking, the double-booking guarantee (incl. a real concurrent race), cancel and rebook."""
import asyncio
import uuid
from datetime import date, time, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from testkit.factories import (
    auth_header,
    future_date,
    make_appointment,
    make_doctor,
    make_user,
)

from app.models import Appointment, AppointmentStatus, Doctor, User
from app.schemas import DayAvailabilityOut, TimeSlotOut
from app.services import booking as booking_service
from app.services.scheduling import clinic_now, weekday_index

API = "/api/v1"
SLOT_TAKEN = "This time slot was just booked. Please select another slot or view recommended doctors."


async def book(client: AsyncClient, headers: dict, doctor: Doctor, day: date, start: str = "09:00", **extra: object):  # type: ignore[no-untyped-def]
    body = {"doctorId": str(doctor.id), "date": day.isoformat(), "startTime": start, "concerns": "Chest tightness"}
    body.update(extra)
    return await client.post(f"{API}/appointments", headers=headers, json=body)


async def set_status(client: AsyncClient, headers: dict, appointment_id: str, status: str):  # type: ignore[no-untyped-def]
    return await client.patch(f"{API}/appointments/{appointment_id}/status", headers=headers, json={"status": status})


async def active_rows(db: AsyncSession, doctor: Doctor, day: date, start: time) -> int:
    stmt = (
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == day,
            Appointment.start_time == start,
            Appointment.status != AppointmentStatus.CANCELLED,
        )
    )
    return (await db.execute(stmt)).scalar_one()


class TestBookingSuccess:
    async def test_books_the_slot_as_confirmed(self, client: AsyncClient, as_patient: dict, patient: User) -> None:
        doctor, day = await make_doctor(specialization="Neurology"), future_date(5)
        response = await book(client, as_patient, doctor, day, "09:30", concerns="  Migraine for 3 days  ")
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "CONFIRMED"
        assert (body["startTime"], body["endTime"], body["date"]) == ("09:30", "10:00", day.isoformat())
        assert body["doctorName"] == doctor.full_name and body["specialization"] == "Neurology"
        assert body["patientId"] == str(patient.id) and body["patientName"] == patient.full_name
        assert body["concerns"] == "Migraine for 3 days"

    async def test_concerns_are_optional(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        response = await client.post(
            f"{API}/appointments",
            headers=as_patient,
            json={"doctorId": str(doctor.id), "date": future_date(5).isoformat(), "startTime": "09:00"},
        )
        assert response.status_code == 201 and response.json()["concerns"] == ""

    async def test_slot_length_comes_from_the_doctors_schedule(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor(slot_minutes=45, start=time(9), end=time(12))
        response = await book(client, as_patient, doctor, future_date(5), "09:45")
        assert response.status_code == 201 and response.json()["endTime"] == "10:30"

    async def test_booking_appears_in_my_appointments_newest_first(
        self, client: AsyncClient, as_patient: dict, as_other_patient: dict
    ) -> None:
        doctor, day = await make_doctor(), future_date(5)
        first = (await book(client, as_patient, doctor, day, "09:00")).json()["id"]
        third = (await book(client, as_patient, doctor, day + timedelta(days=1), "09:30")).json()["id"]
        second = (await book(client, as_patient, doctor, day, "09:30")).json()["id"]
        await book(client, as_other_patient, doctor, day, "10:00")  # someone else's: must not show up
        mine = (await client.get(f"{API}/appointments/me", headers=as_patient)).json()
        assert [a["id"] for a in mine] == [third, second, first]

    async def test_booking_creates_a_confirmation_notification(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        await book(client, as_patient, doctor, future_date(5))
        notes = (await client.get(f"{API}/notifications", headers=as_patient)).json()
        confirmation = next(n for n in notes if n["title"] == "Appointment confirmed")
        assert doctor.full_name in confirmation["message"] and confirmation["read"] is False

    async def test_other_slots_and_other_doctors_remain_bookable(
        self, client: AsyncClient, as_patient: dict, as_other_patient: dict
    ) -> None:
        doctor_a, doctor_b, day = await make_doctor(), await make_doctor(), future_date(5)
        assert (await book(client, as_patient, doctor_a, day, "09:00")).status_code == 201
        assert (await book(client, as_other_patient, doctor_a, day, "09:30")).status_code == 201  # other slot
        assert (await book(client, as_other_patient, doctor_b, day, "09:00")).status_code == 201  # other doctor
        assert (await book(client, as_other_patient, doctor_a, day + timedelta(days=1), "09:00")).status_code == 201  # other day

    async def test_last_bookable_day_is_sixty_days_out(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        edge = clinic_now().date() + timedelta(days=60)
        assert (await book(client, as_patient, doctor, edge)).status_code == 201


class TestDoubleBookingIsRejected:
    async def test_same_slot_twice_is_409(self, client: AsyncClient, as_patient: dict, db: AsyncSession) -> None:
        doctor, day = await make_doctor(), future_date(5)
        assert (await book(client, as_patient, doctor, day)).status_code == 201
        again = await book(client, as_patient, doctor, day)
        assert again.status_code == 409 and again.json() == {"detail": SLOT_TAKEN}
        assert await active_rows(db, doctor, day, time(9)) == 1

    async def test_a_different_patient_cannot_take_a_booked_slot(
        self, client: AsyncClient, as_patient: dict, as_other_patient: dict, db: AsyncSession
    ) -> None:
        doctor, day = await make_doctor(), future_date(5)
        await book(client, as_patient, doctor, day)
        rival = await book(client, as_other_patient, doctor, day)
        assert rival.status_code == 409
        assert await active_rows(db, doctor, day, time(9)) == 1

    async def test_eight_patients_racing_for_one_slot_produce_exactly_one_winner(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        doctor, day = await make_doctor(), future_date(6)
        racers = await asyncio.gather(*[make_user(full_name=f"Racer {i}") for i in range(8)])
        responses = await asyncio.gather(*[book(client, auth_header(p), doctor, day) for p in racers])

        codes = sorted(r.status_code for r in responses)
        assert codes == [201] + [409] * 7
        assert {r.json()["detail"] for r in responses if r.status_code == 409} == {SLOT_TAKEN}
        winner = next(r for r in responses if r.status_code == 201).json()
        assert await active_rows(db, doctor, day, time(9)) == 1
        stored = (
            await db.execute(select(Appointment).where(Appointment.id == uuid.UUID(winner["id"])))
        ).scalar_one()
        assert str(stored.patient_id) == winner["patientId"]

    async def test_same_patient_hammering_one_slot_still_books_it_once(
        self, client: AsyncClient, as_patient: dict, db: AsyncSession
    ) -> None:
        doctor, day = await make_doctor(), future_date(6)
        responses = await asyncio.gather(*[book(client, as_patient, doctor, day) for _ in range(10)])
        assert sorted(r.status_code for r in responses) == [201] + [409] * 9
        assert await active_rows(db, doctor, day, time(9)) == 1

    async def test_the_unique_index_catches_a_booking_that_slipped_past_the_pre_check(
        self, client: AsyncClient, as_patient: dict, as_other_patient: dict, db: AsyncSession, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Simulates the race window: the availability read says 'free' although the row now exists."""
        doctor, day = await make_doctor(), future_date(6)
        assert (await book(client, as_patient, doctor, day)).status_code == 201

        async def stale_view(_db, doctor_id, d):  # type: ignore[no-untyped-def]
            slot = TimeSlotOut(start_time="09:00", end_time="09:30", status="available")
            return doctor.full_name, DayAvailabilityOut(doctor_id=doctor_id, date=d, is_working_day=True, slots=[slot])

        monkeypatch.setattr(booking_service, "load_day", stale_view)
        rival = await book(client, as_other_patient, doctor, day)
        assert rival.status_code == 409 and rival.json() == {"detail": SLOT_TAKEN}
        assert await active_rows(db, doctor, day, time(9)) == 1

    async def test_unexpected_database_errors_are_a_bare_500_with_no_details(
        self, client_no_raise: AsyncClient, as_patient: dict, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        ghost = uuid.uuid4()  # a doctor id that does not exist: the insert violates the foreign key

        async def phantom_view(_db, doctor_id, d):  # type: ignore[no-untyped-def]
            slot = TimeSlotOut(start_time="09:00", end_time="09:30", status="available")
            return "Dr. Ghost", DayAvailabilityOut(doctor_id=doctor_id, date=d, is_working_day=True, slots=[slot])

        monkeypatch.setattr(booking_service, "load_day", phantom_view)
        response = await client_no_raise.post(
            f"{API}/appointments",
            headers=as_patient,
            json={"doctorId": str(ghost), "date": future_date(5).isoformat(), "startTime": "09:00"},
        )
        assert response.status_code == 500
        assert response.text == "Internal Server Error"  # no SQL, table names or values leak out


class TestBookingValidation:
    async def test_past_date_is_422(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        response = await book(client, as_patient, doctor, clinic_now().date() - timedelta(days=1))
        assert response.status_code == 422 and response.json()["detail"] == "Choose a date in the future."

    async def test_more_than_sixty_days_ahead_is_422(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        response = await book(client, as_patient, doctor, clinic_now().date() + timedelta(days=61))
        assert response.status_code == 422 and "too far" in response.json()["detail"]

    async def test_a_time_that_is_not_a_slot_is_422(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        assert (await book(client, as_patient, doctor, future_date(5), "03:07")).status_code == 422
        assert (await book(client, as_patient, doctor, future_date(5), "09:15")).status_code == 422  # between slots

    async def test_break_slot_cannot_be_booked(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor(break_start=time(10), break_end=time(11))
        response = await book(client, as_patient, doctor, future_date(5), "10:00")
        assert response.status_code == 422 and response.json()["detail"] == "This time slot is not available."

    async def test_day_off_and_blocked_date_cannot_be_booked(self, client: AsyncClient, as_patient: dict) -> None:
        day = future_date(5)
        off_day = await make_doctor(working_days=((weekday_index(day) + 1) % 7,))
        blocked = await make_doctor(blocked_dates=(day,))
        assert (await book(client, as_patient, off_day, day)).status_code == 422
        assert (await book(client, as_patient, blocked, day)).status_code == 422

    async def test_unknown_and_inactive_doctors_are_404(self, client: AsyncClient, as_patient: dict) -> None:
        inactive = await make_doctor(is_active=False)
        ghost = await client.post(
            f"{API}/appointments",
            headers=as_patient,
            json={"doctorId": str(uuid.uuid4()), "date": future_date(5).isoformat(), "startTime": "09:00"},
        )
        assert ghost.status_code == 404
        assert (await book(client, as_patient, inactive, future_date(5))).status_code == 404

    async def test_malformed_requests_are_422(self, client: AsyncClient, as_patient: dict) -> None:
        doctor, day = await make_doctor(), future_date(5)
        assert (await book(client, as_patient, doctor, day, "9:00")).status_code == 422
        assert (await book(client, as_patient, doctor, day, concerns="x" * 1001)).status_code == 422
        assert (await client.post(f"{API}/appointments", headers=as_patient, json={})).status_code == 422

    async def test_admins_cannot_book_and_anonymous_callers_are_rejected(
        self, client: AsyncClient, as_admin: dict
    ) -> None:
        doctor, day = await make_doctor(), future_date(5)
        assert (await book(client, as_admin, doctor, day)).status_code == 403
        assert (await book(client, {}, doctor, day)).status_code == 401


class TestCancelAndRebook:
    async def test_patient_cancels_their_own_appointment(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        booked = (await book(client, as_patient, doctor, future_date(5))).json()
        response = await set_status(client, as_patient, booked["id"], "CANCELLED")
        assert response.status_code == 200 and response.json()["status"] == "CANCELLED"

    async def test_cancelled_slot_shows_available_again(self, client: AsyncClient, as_patient: dict) -> None:
        doctor, day = await make_doctor(), future_date(5)
        booked = (await book(client, as_patient, doctor, day)).json()
        url, params = f"{API}/doctors/{doctor.id}/slots", {"date": day.isoformat()}
        before = {s["startTime"]: s["status"] for s in (await client.get(url, headers=as_patient, params=params)).json()["slots"]}
        await set_status(client, as_patient, booked["id"], "CANCELLED")
        after = {s["startTime"]: s["status"] for s in (await client.get(url, headers=as_patient, params=params)).json()["slots"]}
        assert (before["09:00"], after["09:00"]) == ("booked", "available")

    async def test_cancelled_slot_can_be_rebooked_by_anyone(
        self, client: AsyncClient, as_patient: dict, as_other_patient: dict, db: AsyncSession
    ) -> None:
        doctor, day = await make_doctor(), future_date(5)
        first = (await book(client, as_patient, doctor, day)).json()
        await set_status(client, as_patient, first["id"], "CANCELLED")

        rebooked = await book(client, as_other_patient, doctor, day)
        assert rebooked.status_code == 201 and rebooked.json()["id"] != first["id"]
        rows = (await db.execute(select(Appointment.status).where(Appointment.doctor_id == doctor.id))).scalars().all()
        assert sorted(s.value for s in rows) == ["CANCELLED", "CONFIRMED"]  # history kept, slot reused
        assert await active_rows(db, doctor, day, time(9)) == 1

    async def test_the_same_patient_can_rebook_after_cancelling(self, client: AsyncClient, as_patient: dict) -> None:
        doctor, day = await make_doctor(), future_date(5)
        first = (await book(client, as_patient, doctor, day)).json()
        await set_status(client, as_patient, first["id"], "CANCELLED")
        assert (await book(client, as_patient, doctor, day)).status_code == 201

    async def test_cancelling_creates_a_notification(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        booked = (await book(client, as_patient, doctor, future_date(5))).json()
        await set_status(client, as_patient, booked["id"], "CANCELLED")
        titles = [n["title"] for n in (await client.get(f"{API}/notifications", headers=as_patient)).json()]
        assert "Appointment cancelled" in titles

    async def test_cancelling_twice_is_409(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        booked = (await book(client, as_patient, doctor, future_date(5))).json()
        await set_status(client, as_patient, booked["id"], "CANCELLED")
        again = await set_status(client, as_patient, booked["id"], "CANCELLED")
        assert again.status_code == 409
        assert again.json()["detail"] == "Cannot change a cancelled appointment to cancelled."

    async def test_another_patient_gets_404_not_403(
        self, client: AsyncClient, as_patient: dict, as_other_patient: dict
    ) -> None:
        """Same answer as for a non-existent id, so ids cannot be probed."""
        doctor = await make_doctor()
        booked = (await book(client, as_patient, doctor, future_date(5))).json()
        stranger = await set_status(client, as_other_patient, booked["id"], "CANCELLED")
        missing = await set_status(client, as_other_patient, str(uuid.uuid4()), "CANCELLED")
        assert stranger.status_code == missing.status_code == 404
        assert stranger.json() == missing.json() == {"detail": "Appointment not found."}

    async def test_patients_can_only_cancel_never_confirm_or_complete(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        booked = (await book(client, as_patient, doctor, future_date(5))).json()
        for forbidden in ("PENDING", "CONFIRMED", "COMPLETED"):
            response = await set_status(client, as_patient, booked["id"], forbidden)
            assert response.status_code == 403, forbidden
            assert response.json()["detail"] == "Patients can only cancel their appointments."

    async def test_past_appointments_cannot_be_cancelled(self, client: AsyncClient, as_patient: dict, patient: User) -> None:
        doctor = await make_doctor()
        past = await make_appointment(patient, doctor, clinic_now().date() - timedelta(days=1))
        response = await set_status(client, as_patient, str(past.id), "CANCELLED")
        assert response.status_code == 422 and response.json()["detail"] == "Past appointments cannot be cancelled."

    async def test_a_completed_appointment_cannot_be_cancelled(
        self, client: AsyncClient, as_patient: dict, patient: User
    ) -> None:
        doctor = await make_doctor()
        done = await make_appointment(patient, doctor, future_date(5), status=AppointmentStatus.COMPLETED)
        assert (await set_status(client, as_patient, str(done.id), "CANCELLED")).status_code == 409

    async def test_bad_status_and_ids_are_422(self, client: AsyncClient, as_patient: dict) -> None:
        assert (await set_status(client, as_patient, str(uuid.uuid4()), "DONE")).status_code == 422
        assert (await set_status(client, as_patient, "not-a-uuid", "CANCELLED")).status_code == 422
        assert (await set_status(client, as_patient, str(uuid.uuid4()), "cancelled")).status_code == 422
