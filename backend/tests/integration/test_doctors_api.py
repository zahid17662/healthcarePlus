"""Doctor directory, search, reviews and day availability (slot grid)."""
import uuid
from datetime import time, timedelta

from httpx import AsyncClient
from testkit.factories import (
    future_date,
    make_appointment,
    make_doctor,
    make_review,
    unique,
)

from app.models import AppointmentStatus, User
from app.services.scheduling import clinic_now, weekday_index

API = "/api/v1"


async def listing(client: AsyncClient, headers: dict, **params: str) -> list[dict]:
    response = await client.get(f"{API}/doctors", headers=headers, params=params)
    assert response.status_code == 200
    return response.json()


class TestDirectory:
    async def test_lists_active_doctors_and_hides_inactive_ones(self, client: AsyncClient, as_patient: dict) -> None:
        visible, hidden = await make_doctor(), await make_doctor(is_active=False)
        ids = {d["id"] for d in await listing(client, as_patient)}
        assert str(visible.id) in ids
        assert str(hidden.id) not in ids

    async def test_doctor_json_shape_uses_camel_case(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor(rating="4.50")
        await make_review(doctor, 5)
        await make_review(doctor, 4)
        row = next(d for d in await listing(client, as_patient) if d["id"] == str(doctor.id))
        assert row["name"] == doctor.full_name
        assert row["hourlyRate"] == 80.0 and row["experienceYears"] == 7
        assert row["averageRating"] == 4.5 and row["reviewCount"] == 2
        assert row["imageUrl"] == "" and row["subSpecialties"] == ["Echo"]
        assert row["bio"] == "Bio text" and row["isActive"] is True

    async def test_filters_by_specialization(self, client: AsyncClient, as_patient: dict) -> None:
        spec = unique("Spec")
        mine = [await make_doctor(specialization=spec), await make_doctor(specialization=spec)]
        await make_doctor(specialization=unique("Other"))
        result = await listing(client, as_patient, specialization=spec)
        assert {d["id"] for d in result} == {str(d.id) for d in mine}

    async def test_search_matches_name_specialization_and_sub_specialty_case_insensitively(
        self, client: AsyncClient, as_patient: dict
    ) -> None:
        token = unique("tok").upper()
        by_name = await make_doctor(name=f"Dr. {token}")
        by_spec = await make_doctor(specialization=f"Spec {token}")
        by_sub = await make_doctor(sub_specialties=(f"Sub {token}",))
        unrelated = await make_doctor()
        found = {d["id"] for d in await listing(client, as_patient, q=token.lower())}
        assert found == {str(by_name.id), str(by_spec.id), str(by_sub.id)}
        assert str(unrelated.id) not in found

    async def test_search_treats_percent_and_underscore_as_literals(self, client: AsyncClient, as_patient: dict) -> None:
        token = unique("lit")
        literal = await make_doctor(name=f"Dr. {token}_one")
        lookalike = await make_doctor(name=f"Dr. {token}Xone")
        found = {d["id"] for d in await listing(client, as_patient, q=f"{token}_one")}
        assert found == {str(literal.id)}
        assert str(lookalike.id) not in found
        assert await listing(client, as_patient, q="100%") == []

    async def test_search_term_is_length_limited(self, client: AsyncClient, as_patient: dict) -> None:
        response = await client.get(f"{API}/doctors", headers=as_patient, params={"q": "x" * 81})
        assert response.status_code == 422

    async def test_search_and_filter_combine(self, client: AsyncClient, as_patient: dict) -> None:
        spec, token = unique("Spec"), unique("tok")
        match = await make_doctor(name=f"Dr. {token}", specialization=spec)
        await make_doctor(name=f"Dr. {token}", specialization=unique("Elsewhere"))
        result = await listing(client, as_patient, q=token, specialization=spec)
        assert [d["id"] for d in result] == [str(match.id)]

    async def test_specializations_are_distinct_sorted_and_active_only(self, client: AsyncClient, as_patient: dict) -> None:
        shown, hidden = unique("ShownSpec"), unique("HiddenSpec")
        await make_doctor(specialization=shown)
        await make_doctor(specialization=shown)
        await make_doctor(specialization=hidden, is_active=False)
        names = (await client.get(f"{API}/doctors/specializations", headers=as_patient)).json()
        assert names.count(shown) == 1
        assert hidden not in names
        assert names == sorted(names)


class TestSingleDoctor:
    async def test_returns_the_doctor(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        response = await client.get(f"{API}/doctors/{doctor.id}", headers=as_patient)
        assert response.status_code == 200 and response.json()["id"] == str(doctor.id)

    async def test_unknown_inactive_and_malformed_ids(self, client: AsyncClient, as_patient: dict) -> None:
        inactive = await make_doctor(is_active=False)
        unknown = await client.get(f"{API}/doctors/{uuid.uuid4()}", headers=as_patient)
        assert unknown.status_code == 404 and unknown.json() == {"detail": "Doctor not found."}
        assert (await client.get(f"{API}/doctors/{inactive.id}", headers=as_patient)).status_code == 404
        assert (await client.get(f"{API}/doctors/not-a-uuid", headers=as_patient)).status_code == 422


class TestReviews:
    async def test_newest_review_comes_first(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        await make_review(doctor, 3, comment="older")
        await make_review(doctor, 5, comment="newer")
        reviews = (await client.get(f"{API}/doctors/{doctor.id}/reviews", headers=as_patient)).json()
        assert [r["comment"] for r in reviews] == ["newer", "older"]
        assert reviews[0]["rating"] == 5 and reviews[0]["patientName"] == "Reviewer"

    async def test_doctor_without_reviews_has_an_empty_list(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        response = await client.get(f"{API}/doctors/{doctor.id}/reviews", headers=as_patient)
        assert response.status_code == 200 and response.json() == []


async def slots_for(client: AsyncClient, headers: dict, doctor, day) -> dict:  # type: ignore[no-untyped-def]
    response = await client.get(f"{API}/doctors/{doctor.id}/slots", headers=headers, params={"date": day.isoformat()})
    assert response.status_code == 200, response.text
    return response.json()


def status_by_start(body: dict) -> dict[str, str]:
    return {s["startTime"]: s["status"] for s in body["slots"]}


class TestAvailability:
    async def test_working_day_lists_every_slot_as_available(self, client: AsyncClient, as_patient: dict) -> None:
        doctor, day = await make_doctor(start=time(9), end=time(11)), future_date(4)
        body = await slots_for(client, as_patient, doctor, day)
        assert body["isWorkingDay"] is True and body["date"] == day.isoformat()
        assert status_by_start(body) == {"09:00": "available", "09:30": "available", "10:00": "available", "10:30": "available"}

    async def test_each_slot_reports_its_end_time(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor(start=time(9), end=time(10), slot_minutes=20)
        body = await slots_for(client, as_patient, doctor, future_date(4))
        assert [(s["startTime"], s["endTime"]) for s in body["slots"]] == [("09:00", "09:20"), ("09:20", "09:40"), ("09:40", "10:00")]

    async def test_booked_slot_is_marked_booked(self, client: AsyncClient, as_patient: dict, patient: User) -> None:
        doctor, day = await make_doctor(), future_date(4)
        await make_appointment(patient, doctor, day, time(9, 30))
        statuses = status_by_start(await slots_for(client, as_patient, doctor, day))
        assert statuses["09:30"] == "booked" and statuses["09:00"] == "available"

    async def test_cancelled_booking_frees_the_slot(self, client: AsyncClient, as_patient: dict, patient: User) -> None:
        doctor, day = await make_doctor(), future_date(4)
        await make_appointment(patient, doctor, day, time(9), status=AppointmentStatus.CANCELLED)
        assert status_by_start(await slots_for(client, as_patient, doctor, day))["09:00"] == "available"

    async def test_break_slots_are_blocked(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor(start=time(9), end=time(12), break_start=time(10), break_end=time(11))
        statuses = status_by_start(await slots_for(client, as_patient, doctor, future_date(4)))
        assert statuses["10:00"] == statuses["10:30"] == "blocked"
        assert statuses["09:30"] == statuses["11:00"] == "available"

    async def test_day_off_is_not_a_working_day(self, client: AsyncClient, as_patient: dict) -> None:
        day = future_date(4)
        doctor = await make_doctor(working_days=((weekday_index(day) + 1) % 7,))
        body = await slots_for(client, as_patient, doctor, day)
        assert body["isWorkingDay"] is False and body["slots"] == []

    async def test_blocked_date_is_not_a_working_day(self, client: AsyncClient, as_patient: dict) -> None:
        day = future_date(4)
        doctor = await make_doctor(blocked_dates=(day,))
        body = await slots_for(client, as_patient, doctor, day)
        assert body["isWorkingDay"] is False and body["slots"] == []
        assert (await slots_for(client, as_patient, doctor, day + timedelta(days=1)))["isWorkingDay"] is True

    async def test_doctor_without_a_schedule_has_no_working_days(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor(with_schedule=False)
        assert (await slots_for(client, as_patient, doctor, future_date(4)))["isWorkingDay"] is False

    async def test_every_slot_of_a_past_day_is_past(self, client: AsyncClient, as_patient: dict) -> None:
        doctor, yesterday = await make_doctor(), clinic_now().date() - timedelta(days=1)
        assert set(status_by_start(await slots_for(client, as_patient, doctor, yesterday)).values()) == {"past"}

    async def test_today_is_past_then_available_never_the_reverse(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor(start=time(0), end=time(23, 30))
        statuses = [s["status"] for s in (await slots_for(client, as_patient, doctor, clinic_now().date()))["slots"]]
        assert set(statuses) <= {"past", "available"}
        first_available = statuses.index("available") if "available" in statuses else len(statuses)
        assert all(s == "past" for s in statuses[:first_available])
        assert all(s == "available" for s in statuses[first_available:])

    async def test_unknown_and_inactive_doctors_are_404(self, client: AsyncClient, as_patient: dict) -> None:
        inactive = await make_doctor(is_active=False)
        day = future_date(4).isoformat()
        assert (await client.get(f"{API}/doctors/{uuid.uuid4()}/slots", headers=as_patient, params={"date": day})).status_code == 404
        assert (await client.get(f"{API}/doctors/{inactive.id}/slots", headers=as_patient, params={"date": day})).status_code == 404

    async def test_date_parameter_is_required_and_validated(self, client: AsyncClient, as_patient: dict) -> None:
        doctor = await make_doctor()
        url = f"{API}/doctors/{doctor.id}/slots"
        assert (await client.get(url, headers=as_patient)).status_code == 422
        assert (await client.get(url, headers=as_patient, params={"date": "2030-13-45"})).status_code == 422
