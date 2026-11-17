"""Admin routes: appointment oversight and status workflow, doctors, schedules, daily statistics."""
import asyncio
import uuid
from datetime import date, time, timedelta

import pytest
from httpx import AsyncClient
from testkit.factories import future_date, make_appointment, make_doctor, unique

from app.models import AppointmentStatus as S
from app.models import User
from app.services.scheduling import weekday_index

API = "/api/v1/admin"
PUBLIC = "/api/v1"
NEW_DOCTOR = {
    "name": "Dr. Created Through Api",
    "specialization": "Pediatrics",
    "subSpecialties": ["Asthma", "  ", " Vaccines "],
    "experienceYears": 9,
    "bio": "Careful and kind.",
    "hourlyRate": 65.5,
    "imageUrl": "",
    "isActive": True,
}


def next_weekday(index: int, after: int = 3) -> date:
    """The first date at least `after` days out that falls on weekday `index` (0 = Sunday)."""
    day = future_date(after)
    while weekday_index(day) != index:
        day += timedelta(days=1)
    return day


async def admin_set_status(client: AsyncClient, headers: dict, appointment_id: object, status: str):  # type: ignore[no-untyped-def]
    return await client.patch(f"{PUBLIC}/appointments/{appointment_id}/status", headers=headers, json={"status": status})


class TestAppointmentOversight:
    async def test_lists_a_doctors_appointments_in_chronological_order(
        self, client: AsyncClient, as_admin: dict, patient: User
    ) -> None:
        doctor, day = await make_doctor(specialization="Oncology"), future_date(12)
        later = await make_appointment(patient, doctor, day + timedelta(days=1), time(9, 30), concerns="later")
        late = await make_appointment(patient, doctor, day, time(10, 0))
        early = await make_appointment(patient, doctor, day, time(9, 0))
        rows = (await client.get(f"{API}/appointments", headers=as_admin, params={"doctorId": str(doctor.id)})).json()
        assert [r["id"] for r in rows] == [str(early.id), str(late.id), str(later.id)]
        first = rows[0]
        assert first["patientName"] == patient.full_name and first["doctorName"] == doctor.full_name
        assert first["specialization"] == "Oncology" and first["concerns"] == "seeded appointment"

    async def test_filters_by_date_and_status(self, client: AsyncClient, as_admin: dict, patient: User) -> None:
        doctor, day = await make_doctor(), future_date(12)
        await make_appointment(patient, doctor, day, time(9), status=S.PENDING)
        await make_appointment(patient, doctor, day, time(9, 30), status=S.CANCELLED)
        await make_appointment(patient, doctor, day + timedelta(days=1), time(9), status=S.PENDING)
        params = {"doctorId": str(doctor.id)}
        on_day = (await client.get(f"{API}/appointments", headers=as_admin, params={**params, "date": day.isoformat()})).json()
        cancelled = (await client.get(f"{API}/appointments", headers=as_admin, params={**params, "status": "CANCELLED"})).json()
        both = (await client.get(f"{API}/appointments", headers=as_admin, params={**params, "date": day.isoformat(), "status": "PENDING"})).json()
        assert len(on_day) == 2
        assert [r["status"] for r in cancelled] == ["CANCELLED"]
        assert len(both) == 1 and both[0]["status"] == "PENDING"

    async def test_rejects_malformed_filters(self, client: AsyncClient, as_admin: dict) -> None:
        for params in ({"status": "cancelled"}, {"status": "DONE"}, {"date": "nope"}, {"doctorId": "nope"}):
            assert (await client.get(f"{API}/appointments", headers=as_admin, params=params)).status_code == 422, params

    async def test_unfiltered_list_is_allowed_and_bounded(self, client: AsyncClient, as_admin: dict) -> None:
        response = await client.get(f"{API}/appointments", headers=as_admin)
        assert response.status_code == 200 and len(response.json()) <= 500


class TestStatusWorkflow:
    @pytest.mark.parametrize(
        ("start", "target"),
        [(S.PENDING, S.CONFIRMED), (S.PENDING, S.CANCELLED), (S.CONFIRMED, S.COMPLETED), (S.CONFIRMED, S.CANCELLED)],
        ids=lambda s: s.value.lower(),
    )
    async def test_allowed_transitions(self, client: AsyncClient, as_admin: dict, patient: User, start: S, target: S) -> None:
        appt = await make_appointment(patient, await make_doctor(), future_date(8), status=start)
        response = await admin_set_status(client, as_admin, appt.id, target.value)
        assert response.status_code == 200 and response.json()["status"] == target.value

    @pytest.mark.parametrize(
        ("start", "target"),
        [
            (S.PENDING, S.COMPLETED),
            (S.CONFIRMED, S.PENDING),
            (S.COMPLETED, S.CANCELLED),
            (S.COMPLETED, S.CONFIRMED),
            (S.CANCELLED, S.CONFIRMED),
            (S.CANCELLED, S.PENDING),
        ],
        ids=lambda s: s.value.lower(),
    )
    async def test_forbidden_transitions_are_409(self, client: AsyncClient, as_admin: dict, patient: User, start: S, target: S) -> None:
        appt = await make_appointment(patient, await make_doctor(), future_date(8), status=start)
        response = await admin_set_status(client, as_admin, appt.id, target.value)
        assert response.status_code == 409
        assert response.json()["detail"] == f"Cannot change a {start.value.lower()} appointment to {target.value.lower()}."

    async def test_the_patient_is_notified_not_the_admin(
        self, client: AsyncClient, as_admin: dict, as_patient: dict, patient: User
    ) -> None:
        appt = await make_appointment(patient, await make_doctor(), future_date(8), status=S.PENDING)
        await admin_set_status(client, as_admin, appt.id, "CONFIRMED")
        patient_titles = [n["title"] for n in (await client.get(f"{PUBLIC}/notifications", headers=as_patient)).json()]
        admin_titles = [n["title"] for n in (await client.get(f"{PUBLIC}/notifications", headers=as_admin)).json()]
        assert "Appointment confirmed" in patient_titles
        assert "Appointment confirmed" not in admin_titles

    async def test_a_slot_cancelled_by_an_admin_can_be_rebooked(
        self, client: AsyncClient, as_admin: dict, as_other_patient: dict, patient: User
    ) -> None:
        doctor, day = await make_doctor(), future_date(8)
        appt = await make_appointment(patient, doctor, day, time(9), status=S.CONFIRMED)
        await admin_set_status(client, as_admin, appt.id, "CANCELLED")
        rebook = await client.post(
            f"{PUBLIC}/appointments",
            headers=as_other_patient,
            json={"doctorId": str(doctor.id), "date": day.isoformat(), "startTime": "09:00"},
        )
        assert rebook.status_code == 201

    async def test_two_simultaneous_conflicting_changes_cannot_both_win(
        self, client: AsyncClient, as_admin: dict, patient: User
    ) -> None:
        """Row locking: complete vs cancel on the same CONFIRMED appointment -> one 200, one 409."""
        appt = await make_appointment(patient, await make_doctor(), future_date(8), status=S.CONFIRMED)
        results = await asyncio.gather(
            admin_set_status(client, as_admin, appt.id, "COMPLETED"),
            admin_set_status(client, as_admin, appt.id, "CANCELLED"),
        )
        assert sorted(r.status_code for r in results) == [200, 409]

    async def test_unknown_appointment_is_404_and_bad_status_is_422(self, client: AsyncClient, as_admin: dict) -> None:
        assert (await admin_set_status(client, as_admin, uuid.uuid4(), "CONFIRMED")).status_code == 404
        assert (await admin_set_status(client, as_admin, uuid.uuid4(), "DONE")).status_code == 422


class TestDoctorManagement:
    async def test_admin_list_includes_inactive_doctors(self, client: AsyncClient, as_admin: dict) -> None:
        active, inactive = await make_doctor(), await make_doctor(is_active=False)
        ids = {d["id"] for d in (await client.get(f"{API}/doctors", headers=as_admin)).json()}
        assert {str(active.id), str(inactive.id)} <= ids

    async def test_creates_a_doctor_with_a_default_schedule(self, client: AsyncClient, as_admin: dict, as_patient: dict) -> None:
        response = await client.post(f"{API}/doctors", headers=as_admin, json=NEW_DOCTOR)
        assert response.status_code == 201
        doctor = response.json()
        assert doctor["name"] == NEW_DOCTOR["name"] and doctor["hourlyRate"] == 65.5
        assert doctor["subSpecialties"] == ["Asthma", "Vaccines"]  # blanks dropped, whitespace trimmed
        assert (doctor["averageRating"], doctor["reviewCount"], doctor["imageUrl"]) == (0.0, 0, "")

        schedule = (await client.get(f"{API}/doctors/{doctor['id']}/schedule", headers=as_admin)).json()
        assert (schedule["workingDays"], schedule["startTime"], schedule["endTime"], schedule["slotMinutes"]) == ([1, 2, 3, 4, 5], "09:00", "17:00", 30)
        assert (schedule["breakStart"], schedule["breakEnd"]) == ("13:00", "14:00")

        monday = next_weekday(1)
        slots = (await client.get(f"{PUBLIC}/doctors/{doctor['id']}/slots", headers=as_patient, params={"date": monday.isoformat()})).json()["slots"]
        assert len(slots) == 16 and [s["startTime"] for s in slots if s["status"] == "blocked"] == ["13:00", "13:30"]

    async def test_created_doctor_is_visible_to_patients(self, client: AsyncClient, as_admin: dict, as_patient: dict) -> None:
        created = (await client.post(f"{API}/doctors", headers=as_admin, json={**NEW_DOCTOR, "name": f"Dr. {unique('vis')}"})).json()
        public = (await client.get(f"{PUBLIC}/doctors/{created['id']}", headers=as_patient))
        assert public.status_code == 200

    async def test_stores_an_https_image_url(self, client: AsyncClient, as_admin: dict) -> None:
        response = await client.post(f"{API}/doctors", headers=as_admin, json={**NEW_DOCTOR, "imageUrl": "https://cdn.example.com/dr.jpg"})
        assert response.json()["imageUrl"] == "https://cdn.example.com/dr.jpg"

    @pytest.mark.parametrize(
        "override",
        [
            {"name": "Dr"},
            {"hourlyRate": 0},
            {"hourlyRate": -3},
            {"experienceYears": -1},
            {"imageUrl": "javascript:alert(1)"},
            {"specialization": ""},
        ],
        ids=["short-name", "zero-rate", "negative-rate", "negative-experience", "javascript-url", "blank-specialty"],
    )
    async def test_invalid_doctors_are_422(self, client: AsyncClient, as_admin: dict, override: dict) -> None:
        assert (await client.post(f"{API}/doctors", headers=as_admin, json={**NEW_DOCTOR, **override})).status_code == 422

    async def test_updates_a_doctor_and_keeps_their_rating(self, client: AsyncClient, as_admin: dict) -> None:
        from testkit.factories import make_review

        doctor = await make_doctor(rating="4.00")
        await make_review(doctor, 4)
        response = await client.put(f"{API}/doctors/{doctor.id}", headers=as_admin, json={**NEW_DOCTOR, "name": "Dr. Renamed", "hourlyRate": 99})
        assert response.status_code == 200
        body = response.json()
        assert (body["name"], body["hourlyRate"], body["reviewCount"]) == ("Dr. Renamed", 99.0, 1)
        listed = {d["id"]: d for d in (await client.get(f"{API}/doctors", headers=as_admin)).json()}
        assert listed[str(doctor.id)]["name"] == "Dr. Renamed"

    async def test_deactivating_hides_the_doctor_from_patients_and_reactivating_restores_them(
        self, client: AsyncClient, as_admin: dict, as_patient: dict
    ) -> None:
        doctor = await make_doctor()
        url = f"{PUBLIC}/doctors/{doctor.id}"
        await client.put(f"{API}/doctors/{doctor.id}", headers=as_admin, json={**NEW_DOCTOR, "isActive": False})
        assert (await client.get(url, headers=as_patient)).status_code == 404
        await client.put(f"{API}/doctors/{doctor.id}", headers=as_admin, json={**NEW_DOCTOR, "isActive": True})
        assert (await client.get(url, headers=as_patient)).status_code == 200

    async def test_update_of_unknown_doctor_is_404_and_invalid_body_is_422(self, client: AsyncClient, as_admin: dict) -> None:
        assert (await client.put(f"{API}/doctors/{uuid.uuid4()}", headers=as_admin, json=NEW_DOCTOR)).status_code == 404
        doctor = await make_doctor()
        assert (await client.put(f"{API}/doctors/{doctor.id}", headers=as_admin, json={**NEW_DOCTOR, "hourlyRate": 0})).status_code == 422


class TestScheduleManagement:
    async def schedule(self, client: AsyncClient, headers: dict, doctor) -> dict:  # type: ignore[no-untyped-def]
        response = await client.get(f"{API}/doctors/{doctor.id}/schedule", headers=headers)
        assert response.status_code == 200
        return response.json()

    async def put(self, client: AsyncClient, headers: dict, doctor, **changes: object):  # type: ignore[no-untyped-def]
        current = await self.schedule(client, headers, doctor)
        return await client.put(f"{API}/doctors/{doctor.id}/schedule", headers=headers, json={**current, **changes})

    async def test_reads_the_current_schedule(self, client: AsyncClient, as_admin: dict) -> None:
        blocked = future_date(9)
        doctor = await make_doctor(working_days=(3, 1), start=time(8, 30), end=time(12), slot_minutes=20,
                                   break_start=time(10), break_end=time(10, 20), blocked_dates=(blocked,))
        body = await self.schedule(client, as_admin, doctor)
        assert body == {
            "doctorId": str(doctor.id), "workingDays": [1, 3], "startTime": "08:30", "endTime": "12:00",
            "slotMinutes": 20, "breakStart": "10:00", "breakEnd": "10:20", "blockedDates": [blocked.isoformat()],
        }

    async def test_changing_slot_length_and_hours_regenerates_the_slots(self, client: AsyncClient, as_admin: dict, as_patient: dict) -> None:
        doctor, day = await make_doctor(), future_date(9)
        response = await self.put(client, as_admin, doctor, startTime="09:00", endTime="10:00", slotMinutes=20)
        assert response.status_code == 200 and response.json()["slotMinutes"] == 20
        slots = (await client.get(f"{PUBLIC}/doctors/{doctor.id}/slots", headers=as_patient, params={"date": day.isoformat()})).json()["slots"]
        assert [(s["startTime"], s["endTime"]) for s in slots] == [("09:00", "09:20"), ("09:20", "09:40"), ("09:40", "10:00")]

    async def test_working_days_decide_which_days_have_slots(self, client: AsyncClient, as_admin: dict, as_patient: dict) -> None:
        doctor, day = await make_doctor(), future_date(9)
        await self.put(client, as_admin, doctor, workingDays=[(weekday_index(day) + 1) % 7, (weekday_index(day) + 1) % 7])
        body = (await client.get(f"{PUBLIC}/doctors/{doctor.id}/slots", headers=as_patient, params={"date": day.isoformat()})).json()
        assert body["isWorkingDay"] is False
        assert (await self.schedule(client, as_admin, doctor))["workingDays"] == [(weekday_index(day) + 1) % 7]  # de-duplicated

    async def test_adding_a_break_blocks_those_slots(self, client: AsyncClient, as_admin: dict, as_patient: dict) -> None:
        doctor, day = await make_doctor(), future_date(9)
        await self.put(client, as_admin, doctor, breakStart="10:00", breakEnd="11:00")
        slots = (await client.get(f"{PUBLIC}/doctors/{doctor.id}/slots", headers=as_patient, params={"date": day.isoformat()})).json()["slots"]
        assert {s["startTime"]: s["status"] for s in slots}["10:30"] == "blocked"

    async def test_blocked_dates_are_replaced_not_appended(self, client: AsyncClient, as_admin: dict, as_patient: dict) -> None:
        doctor, first, second = await make_doctor(), future_date(9), future_date(10)
        await self.put(client, as_admin, doctor, blockedDates=[first.isoformat()])
        await self.put(client, as_admin, doctor, blockedDates=[second.isoformat(), second.isoformat()])
        assert (await self.schedule(client, as_admin, doctor))["blockedDates"] == [second.isoformat()]
        reopened = (await client.get(f"{PUBLIC}/doctors/{doctor.id}/slots", headers=as_patient, params={"date": first.isoformat()})).json()
        assert reopened["isWorkingDay"] is True
        await self.put(client, as_admin, doctor, blockedDates=[])
        assert (await self.schedule(client, as_admin, doctor))["blockedDates"] == []

    async def test_existing_bookings_survive_a_schedule_change(self, client: AsyncClient, as_admin: dict, patient: User) -> None:
        doctor, day = await make_doctor(), future_date(9)
        appt = await make_appointment(patient, doctor, day, time(9))
        await self.put(client, as_admin, doctor, startTime="10:00", endTime="12:00")
        rows = (await client.get(f"{API}/appointments", headers=as_admin, params={"doctorId": str(doctor.id)})).json()
        assert [r["id"] for r in rows] == [str(appt.id)]

    @pytest.mark.parametrize(
        "changes",
        [
            {"startTime": "12:00", "endTime": "09:00"},
            {"startTime": "09:00", "endTime": "09:00"},
            {"breakStart": "10:00", "breakEnd": None},
            {"breakStart": None, "breakEnd": "10:00"},
            {"breakStart": "11:00", "breakEnd": "10:00"},
            {"slotMinutes": 9},
            {"slotMinutes": 121},
            {"workingDays": [7]},
            {"startTime": "9am"},
        ],
        ids=["end-before-start", "zero-length", "break-start-only", "break-end-only", "break-inverted", "slot-too-short", "slot-too-long", "bad-weekday", "bad-time"],
    )
    async def test_invalid_schedules_are_422(self, client: AsyncClient, as_admin: dict, changes: dict) -> None:
        doctor = await make_doctor()
        assert (await self.put(client, as_admin, doctor, **changes)).status_code == 422

    async def test_invalid_update_leaves_the_schedule_unchanged(self, client: AsyncClient, as_admin: dict) -> None:
        doctor = await make_doctor()
        before = await self.schedule(client, as_admin, doctor)
        await self.put(client, as_admin, doctor, startTime="12:00", endTime="09:00")
        assert await self.schedule(client, as_admin, doctor) == before

    async def test_unknown_doctor_is_404_for_read_and_write(self, client: AsyncClient, as_admin: dict) -> None:
        ghost = uuid.uuid4()
        assert (await client.get(f"{API}/doctors/{ghost}/schedule", headers=as_admin)).status_code == 404
        body = {"doctorId": str(ghost), "workingDays": [1], "startTime": "09:00", "endTime": "10:00", "slotMinutes": 30}
        assert (await client.put(f"{API}/doctors/{ghost}/schedule", headers=as_admin, json=body)).status_code == 404

    async def test_doctor_without_a_schedule_can_be_given_one(self, client: AsyncClient, as_admin: dict, as_patient: dict) -> None:
        doctor, day = await make_doctor(with_schedule=False), future_date(9)
        assert (await client.get(f"{API}/doctors/{doctor.id}/schedule", headers=as_admin)).status_code == 404
        body = {"doctorId": str(doctor.id), "workingDays": list(range(7)), "startTime": "09:00", "endTime": "10:00", "slotMinutes": 30}
        assert (await client.put(f"{API}/doctors/{doctor.id}/schedule", headers=as_admin, json=body)).status_code == 200
        slots = (await client.get(f"{PUBLIC}/doctors/{doctor.id}/slots", headers=as_patient, params={"date": day.isoformat()})).json()["slots"]
        assert [s["startTime"] for s in slots] == ["09:00", "09:30"]


class TestDailyStatistics:
    async def test_an_empty_day_is_all_zeros(self, clean_db: None, client: AsyncClient, as_admin: dict) -> None:
        day = future_date(10)
        stats = (await client.get(f"{API}/stats/daily", headers=as_admin, params={"date": day.isoformat()})).json()
        assert (stats["totalBookings"], stats["cancelled"], stats["cancellationRate"], stats["activeDoctors"]) == (0, 0, 0.0, 0)
        assert stats["bySpecialty"] == []
        assert [d["date"] for d in stats["last7Days"]] == [(day - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        assert all(d["bookings"] == d["cancelled"] == 0 for d in stats["last7Days"])

    async def test_counts_statuses_specialties_rate_and_trend(
        self, clean_db: None, client: AsyncClient, as_admin: dict, patient: User
    ) -> None:
        day = future_date(10)
        heart, brain = unique("Heart"), unique("Brain")
        a, b = await make_doctor(specialization=heart), await make_doctor(specialization=heart)
        c = await make_doctor(specialization=brain)
        await make_doctor(specialization=heart, working_days=((weekday_index(day) + 1) % 7,))  # day off
        await make_doctor(specialization=heart, blocked_dates=(day,))  # blocked that day
        await make_doctor(specialization=heart, is_active=False)  # inactive
        await make_appointment(patient, a, day, time(9), status=S.CONFIRMED)
        await make_appointment(patient, a, day, time(9, 30), status=S.CONFIRMED)
        await make_appointment(patient, b, day, time(9), status=S.PENDING)
        await make_appointment(patient, c, day, time(9), status=S.COMPLETED)
        await make_appointment(patient, c, day, time(9, 30), status=S.CANCELLED)
        await make_appointment(patient, a, day - timedelta(days=1), time(9), status=S.CONFIRMED)
        await make_appointment(patient, a, day - timedelta(days=1), time(9, 30), status=S.CANCELLED)
        await make_appointment(patient, a, day - timedelta(days=3), time(9), status=S.COMPLETED)

        stats = (await client.get(f"{API}/stats/daily", headers=as_admin, params={"date": day.isoformat()})).json()
        assert (stats["totalBookings"], stats["confirmed"], stats["pending"], stats["completed"], stats["cancelled"]) == (5, 2, 1, 1, 1)
        assert stats["cancellationRate"] == pytest.approx(0.2)
        assert stats["bySpecialty"] == sorted(
            [{"specialization": heart, "count": 3}, {"specialization": brain, "count": 1}], key=lambda s: -s["count"]
        )  # cancelled bookings do not count as demand
        assert stats["activeDoctors"] == 3  # a, b, c only
        trend = {d["date"]: (d["bookings"], d["cancelled"]) for d in stats["last7Days"]}
        assert trend[day.isoformat()] == (5, 1)
        assert trend[(day - timedelta(days=1)).isoformat()] == (2, 1)
        assert trend[(day - timedelta(days=3)).isoformat()] == (1, 0)
        assert trend[(day - timedelta(days=2)).isoformat()] == (0, 0)

    async def test_date_is_required(self, client: AsyncClient, as_admin: dict) -> None:
        assert (await client.get(f"{API}/stats/daily", headers=as_admin)).status_code == 422
