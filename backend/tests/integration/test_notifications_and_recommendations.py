"""In-app notifications and the same-specialty doctor recommendation engine."""
import uuid
from datetime import time, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from testkit.factories import future_date, make_appointment, make_doctor, unique

from app.models import Notification, User
from app.services.scheduling import clinic_now

API = "/api/v1"


class TestNotifications:
    async def test_lists_only_the_callers_notifications_newest_first(
        self, client: AsyncClient, as_patient: dict, patient: User, other_patient: User, db: AsyncSession
    ) -> None:
        db.add_all(
            [
                Notification(user_id=patient.id, title="first", message="m"),
                Notification(user_id=other_patient.id, title="someone else's", message="m"),
            ]
        )
        await db.commit()
        db.add(Notification(user_id=patient.id, title="second", message="m"))
        await db.commit()
        titles = [n["title"] for n in (await client.get(f"{API}/notifications", headers=as_patient)).json()]
        assert titles == ["second", "first"]

    async def test_at_most_twenty_are_returned(self, client: AsyncClient, as_patient: dict, patient: User, db: AsyncSession) -> None:
        db.add_all([Notification(user_id=patient.id, title=f"n{i}", message="m") for i in range(25)])
        await db.commit()
        assert len((await client.get(f"{API}/notifications", headers=as_patient)).json()) == 20

    async def test_notification_json_shape(self, client: AsyncClient, as_patient: dict, patient: User, db: AsyncSession) -> None:
        db.add(Notification(user_id=patient.id, title="Hello", message="World"))
        await db.commit()
        note = (await client.get(f"{API}/notifications", headers=as_patient)).json()[0]
        assert set(note) == {"id", "userId", "title", "message", "read", "createdAt"}
        assert note["read"] is False and note["userId"] == str(patient.id)

    async def test_read_all_marks_only_my_notifications(
        self, client: AsyncClient, as_patient: dict, as_other_patient: dict, patient: User, other_patient: User, db: AsyncSession
    ) -> None:
        db.add_all(
            [
                Notification(user_id=patient.id, title="mine", message="m"),
                Notification(user_id=other_patient.id, title="theirs", message="m"),
            ]
        )
        await db.commit()
        assert (await client.post(f"{API}/notifications/read-all", headers=as_patient)).status_code == 204
        mine = (await client.get(f"{API}/notifications", headers=as_patient)).json()
        theirs = (await client.get(f"{API}/notifications", headers=as_other_patient)).json()
        assert all(n["read"] for n in mine)
        assert not any(n["read"] for n in theirs)

    async def test_read_all_is_idempotent_and_fine_when_empty(self, client: AsyncClient, as_patient: dict) -> None:
        assert (await client.post(f"{API}/notifications/read-all", headers=as_patient)).status_code == 204
        assert (await client.post(f"{API}/notifications/read-all", headers=as_patient)).status_code == 204


async def recommend(client: AsyncClient, headers: dict, doctor, day):  # type: ignore[no-untyped-def]
    return await client.get(
        f"{API}/recommendations", headers=headers, params={"doctorId": str(doctor.id), "date": day.isoformat()}
    )


class TestRecommendations:
    async def test_returns_other_active_doctors_of_the_same_specialty_only(
        self, client: AsyncClient, as_patient: dict
    ) -> None:
        spec, day = unique("Spec"), future_date(6)
        requested = await make_doctor(specialization=spec)
        same = await make_doctor(specialization=spec)
        await make_doctor(specialization=unique("Other"))  # different specialty
        await make_doctor(specialization=spec, is_active=False)  # inactive
        body = (await recommend(client, as_patient, requested, day)).json()
        assert [r["doctor"]["id"] for r in body] == [str(same.id)]

    async def test_never_recommends_the_requested_doctor(self, client: AsyncClient, as_patient: dict) -> None:
        spec = unique("Spec")
        solo = await make_doctor(specialization=spec)
        assert (await recommend(client, as_patient, solo, future_date(6))).json() == []

    async def test_each_item_has_a_full_doctor_a_date_and_a_start_time(self, client: AsyncClient, as_patient: dict) -> None:
        spec, day = unique("Spec"), future_date(6)
        requested, alternative = await make_doctor(specialization=spec), await make_doctor(specialization=spec, start=time(10), end=time(12))
        item = (await recommend(client, as_patient, requested, day)).json()[0]
        assert (item["date"], item["startTime"]) == (day.isoformat(), "10:00")
        assert item["doctor"]["id"] == str(alternative.id) and item["doctor"]["name"] == alternative.full_name

    async def test_ranked_by_earliest_slot_then_by_rating(self, client: AsyncClient, as_patient: dict) -> None:
        spec, day = unique("Spec"), future_date(6)
        requested = await make_doctor(specialization=spec)
        later_but_top_rated = await make_doctor(specialization=spec, start=time(10), end=time(12), rating="5.00")
        early_low = await make_doctor(specialization=spec, rating="3.00")
        early_high = await make_doctor(specialization=spec, rating="4.50")
        order = [r["doctor"]["id"] for r in (await recommend(client, as_patient, requested, day)).json()]
        assert order == [str(early_high.id), str(early_low.id), str(later_but_top_rated.id)]

    async def test_returns_at_most_three(self, client: AsyncClient, as_patient: dict) -> None:
        spec = unique("Spec")
        requested = await make_doctor(specialization=spec)
        for _ in range(5):
            await make_doctor(specialization=spec)
        assert len((await recommend(client, as_patient, requested, future_date(6))).json()) == 3

    async def test_skips_booked_slots_to_find_the_next_free_one(
        self, client: AsyncClient, as_patient: dict, patient: User
    ) -> None:
        spec, day = unique("Spec"), future_date(6)
        requested, alternative = await make_doctor(specialization=spec), await make_doctor(specialization=spec)
        await make_appointment(patient, alternative, day, time(9, 0))
        item = (await recommend(client, as_patient, requested, day)).json()[0]
        assert (item["date"], item["startTime"]) == (day.isoformat(), "09:30")

    async def test_rolls_to_the_next_day_when_the_whole_day_is_full(
        self, client: AsyncClient, as_patient: dict, patient: User
    ) -> None:
        spec, day = unique("Spec"), future_date(6)
        requested = await make_doctor(specialization=spec)
        alternative = await make_doctor(specialization=spec, start=time(9), end=time(9, 30))  # a single slot per day
        await make_appointment(patient, alternative, day, time(9, 0))
        item = (await recommend(client, as_patient, requested, day)).json()[0]
        assert (item["date"], item["startTime"]) == ((day + timedelta(days=1)).isoformat(), "09:00")

    async def test_respects_blocked_dates(self, client: AsyncClient, as_patient: dict) -> None:
        spec, day = unique("Spec"), future_date(6)
        requested = await make_doctor(specialization=spec)
        await make_doctor(specialization=spec, blocked_dates=(day,))
        item = (await recommend(client, as_patient, requested, day)).json()[0]
        assert item["date"] == (day + timedelta(days=1)).isoformat()

    async def test_gives_up_after_fourteen_days_of_nothing_free(self, client: AsyncClient, as_patient: dict) -> None:
        spec, day = unique("Spec"), future_date(6)
        requested = await make_doctor(specialization=spec)
        await make_doctor(specialization=spec, blocked_dates=tuple(day + timedelta(days=i) for i in range(15)))
        assert (await recommend(client, as_patient, requested, day)).json() == []

    async def test_a_past_start_date_is_clamped_to_today(self, client: AsyncClient, as_patient: dict) -> None:
        spec, today = unique("Spec"), clinic_now().date()
        requested = await make_doctor(specialization=spec)
        await make_doctor(specialization=spec, start=time(0), end=time(23, 30))
        items = (await recommend(client, as_patient, requested, today - timedelta(days=30))).json()
        assert items and all(i["date"] >= today.isoformat() for i in items)

    async def test_today_only_offers_slots_later_than_now(self, client: AsyncClient, as_patient: dict) -> None:
        spec, now = unique("Spec"), clinic_now()
        requested = await make_doctor(specialization=spec)
        await make_doctor(specialization=spec, start=time(0), end=time(23, 30))
        item = (await recommend(client, as_patient, requested, now.date())).json()[0]
        # ISO dates and HH:MM strings sort chronologically, so tuple comparison is a time comparison.
        assert (item["date"], item["startTime"]) > (now.date().isoformat(), now.strftime("%H:%M"))

    async def test_unknown_doctor_is_404_and_params_are_required(self, client: AsyncClient, as_patient: dict) -> None:
        ghost = await client.get(
            f"{API}/recommendations", headers=as_patient, params={"doctorId": str(uuid.uuid4()), "date": future_date(6).isoformat()}
        )
        assert ghost.status_code == 404
        assert (await client.get(f"{API}/recommendations", headers=as_patient)).status_code == 422
