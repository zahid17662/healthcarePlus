"""Live end-to-end checks against a running API (default http://127.0.0.1:8000).

Creates throw-away patients and releases the slots it books by cancelling them afterwards.
Run:  .venv/Scripts/python scripts/smoke_test.py
"""
import asyncio
import re
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ROOT = Path(__file__).resolve().parents[1]
results: list[tuple[bool, str]] = []
created_emails: list[str] = []


def check(ok: bool, label: str) -> None:
    results.append((ok, label))
    print(("PASS " if ok else "FAIL ") + label)


def admin_credentials() -> tuple[str, str]:
    text = (ROOT / ".admin-credentials.txt").read_text()
    return re.search(r"email: (.+)", text).group(1).strip(), re.search(r"password: (.+)", text).group(1).strip()


async def find_open_slot(c: httpx.AsyncClient, headers: dict, doctor_id: str) -> tuple[str, str]:
    for offset in range(1, 15):
        day = (date.today() + timedelta(days=offset)).isoformat()
        av = (await c.get(f"/doctors/{doctor_id}/slots", headers=headers, params={"date": day})).json()
        open_slots = [s for s in av["slots"] if s["status"] == "available"]
        if open_slots:
            return day, open_slots[0]["startTime"]
    raise RuntimeError("no open slot in the next two weeks")


async def delete_test_users() -> None:
    """Remove exactly the users this run created (appointments/notifications cascade)."""
    sys.path.insert(0, str(ROOT))
    from sqlalchemy import delete

    from app.db import SessionFactory, engine
    from app.models import User

    async with SessionFactory() as session:
        result = await session.execute(delete(User).where(User.email.in_(created_emails)))
        await session.commit()
    await engine.dispose()
    print(f"cleanup: removed {result.rowcount} test user(s) and their appointments")


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        # --- auth ---
        check((await c.get("/doctors")).status_code == 401, "doctors requires auth (401 without token)")
        email = f"smoke-{uuid.uuid4().hex[:8]}@example.com"
        created_emails.append(email)
        pw = "Sm0ke-Test-Pass"
        r = await c.post("/auth/register", json={"fullName": "Smoke Patient", "email": email, "password": pw})
        check(r.status_code == 201 and r.json()["user"]["role"] == "PATIENT", "register creates a PATIENT")
        check((await c.post("/auth/register", json={"fullName": "X Y", "email": email, "password": pw})).status_code == 409, "duplicate email -> 409")
        check((await c.post("/auth/register", json={"fullName": "X Y", "email": "a@b.test", "password": "short"})).status_code == 422, "weak password -> 422")
        check((await c.post("/auth/login", json={"email": email, "password": "wrong-password"})).status_code == 401, "wrong password -> 401")
        r = await c.post("/auth/login", json={"email": email, "password": pw})
        patient = {"Authorization": f"Bearer {r.json()['token']}"}
        check(r.status_code == 200, "login succeeds")

        # --- directory ---
        docs = (await c.get("/doctors", headers=patient)).json()
        check(len(docs) == 8, f"8 doctors listed (got {len(docs)})")
        card = (await c.get("/doctors", headers=patient, params={"specialization": "Cardiology"})).json()
        check(len(card) == 2 and all(d["specialization"] == "Cardiology" for d in card), "specialization filter")
        check(len((await c.get("/doctors", headers=patient, params={"q": "nadia"})).json()) == 1, "name search")
        check(len((await c.get("/doctors", headers=patient, params={"q": "100%"})).json()) == 0, "LIKE wildcard is escaped")
        doctor = next(d for d in docs if d["name"] == "Dr. Sarah Ahmed")
        check(doctor["reviewCount"] == 3 and doctor["averageRating"] == 4.67, "rating aggregate from reviews")

        target, slot = await find_open_slot(c, patient, doctor["id"])
        check(True, f"found open slot {target} {slot}")

        # --- booking + duplicate prevention ---
        body = {"doctorId": doctor["id"], "date": target, "startTime": slot, "concerns": "Chest tightness on stairs"}
        r = await c.post("/appointments", headers=patient, json=body)
        check(r.status_code == 201 and r.json()["status"] == "CONFIRMED", "booking -> 201 CONFIRMED")
        appt_id = r.json()["id"]
        check((await c.post("/appointments", headers=patient, json=body)).status_code == 409, "same slot again -> 409")
        av = (await c.get(f"/doctors/{doctor['id']}/slots", headers=patient, params={"date": target})).json()
        check(next(s for s in av["slots"] if s["startTime"] == slot)["status"] == "booked", "slot now shows booked")

        # --- concurrency: 12 simultaneous requests for one fresh slot; exactly one may win ---
        fresh = [s for s in av["slots"] if s["status"] == "available"][0]["startTime"]
        race = {"doctorId": doctor["id"], "date": target, "startTime": fresh, "concerns": "race"}
        responses = await asyncio.gather(*[c.post("/appointments", headers=patient, json=race) for _ in range(12)])
        codes = [x.status_code for x in responses]
        check(codes.count(201) == 1 and codes.count(409) == 11, f"12 concurrent bookings -> one 201, eleven 409 (got {codes.count(201)}/{codes.count(409)})")

        # --- validation / authz edges ---
        check((await c.post("/appointments", headers=patient, json={**body, "date": "2020-01-01"})).status_code == 422, "past date -> 422")
        check((await c.post("/appointments", headers=patient, json={**body, "startTime": "03:07"})).status_code == 422, "non-existent slot -> 422")
        check((await c.get("/admin/stats/daily", headers=patient, params={"date": target})).status_code == 403, "patient blocked from admin")
        check((await c.patch(f"/appointments/{appt_id}/status", headers=patient, json={"status": "COMPLETED"})).status_code == 403, "patient cannot complete")

        # --- cancel frees the slot for rebooking ---
        r = await c.patch(f"/appointments/{appt_id}/status", headers=patient, json={"status": "CANCELLED"})
        check(r.status_code == 200 and r.json()["status"] == "CANCELLED", "patient cancels own appointment")
        check((await c.patch(f"/appointments/{appt_id}/status", headers=patient, json={"status": "CANCELLED"})).status_code == 409, "cancel twice -> 409")
        r = await c.post("/appointments", headers=patient, json=body)
        check(r.status_code == 201, "cancelled slot can be rebooked (partial unique index)")
        rebooked = r.json()["id"]

        # --- recommendations: same specialty, never the requested doctor ---
        rec = (await c.get("/recommendations", headers=patient, params={"doctorId": doctor["id"], "date": target})).json()
        check(len(rec) >= 1 and all(x["doctor"]["specialization"] == "Cardiology" and x["doctor"]["id"] != doctor["id"] for x in rec), f"recommendations: {len(rec)} same-specialty alternative(s)")

        # --- notifications ---
        notes = (await c.get("/notifications", headers=patient)).json()
        check(len(notes) >= 3, f"notifications recorded ({len(notes)})")
        check((await c.post("/notifications/read-all", headers=patient)).status_code == 204, "mark all read")

        # --- another patient cannot touch my appointment ---
        other_email = f"o-{uuid.uuid4().hex[:6]}@example.com"
        created_emails.append(other_email)
        other = await c.post("/auth/register", json={"fullName": "Other Person", "email": other_email, "password": pw})
        oh = {"Authorization": f"Bearer {other.json()['token']}"}
        check((await c.patch(f"/appointments/{rebooked}/status", headers=oh, json={"status": "CANCELLED"})).status_code == 404, "other patient gets 404 on my appointment")

        # --- admin ---
        ae, ap = admin_credentials()
        r = await c.post("/auth/login", json={"email": ae, "password": ap})
        admin = {"Authorization": f"Bearer {r.json()['token']}"}
        check(r.status_code == 200 and r.json()["user"]["role"] == "ADMIN", "admin login")
        lst = (await c.get("/admin/appointments", headers=admin, params={"date": target})).json()
        check(any(a["id"] == rebooked for a in lst), "admin sees the booking")
        r = await c.patch(f"/appointments/{rebooked}/status", headers=admin, json={"status": "COMPLETED"})
        check(r.status_code == 200 and r.json()["status"] == "COMPLETED", "admin CONFIRMED -> COMPLETED")
        r = await c.patch(f"/appointments/{rebooked}/status", headers=admin, json={"status": "CANCELLED"})
        check(r.status_code == 409, "admin COMPLETED -> CANCELLED rejected (409)")
        stats = (await c.get("/admin/stats/daily", headers=admin, params={"date": target})).json()
        check(stats["totalBookings"] >= 3 and len(stats["last7Days"]) == 7 and stats["completed"] >= 1, f"daily stats (total={stats['totalBookings']}, completed={stats['completed']})")
        sch = (await c.get(f"/admin/doctors/{doctor['id']}/schedule", headers=admin)).json()
        check(sch["startTime"] == "09:00" and sch["slotMinutes"] == 30, "admin reads schedule config")
        check((await c.put(f"/admin/doctors/{doctor['id']}/schedule", headers=admin, json={**sch, "blockedDates": [target]})).status_code == 200, "admin blocks a date")
        av = (await c.get(f"/doctors/{doctor['id']}/slots", headers=patient, params={"date": target})).json()
        check(av["isWorkingDay"] is False, "blocked date reports not working")
        check((await c.put(f"/admin/doctors/{doctor['id']}/schedule", headers=admin, json=sch)).status_code == 200, "admin restores schedule")
        bad = {"name": "Dr. Bad", "specialization": "Cardiology", "experienceYears": 1, "hourlyRate": 10}
        check((await c.post("/admin/doctors", headers=admin, json={**bad, "name": "X"})).status_code == 422, "invalid doctor payload -> 422")
        check((await c.post("/admin/doctors", headers=admin, json={**bad, "imageUrl": "javascript:alert(1)"})).status_code == 422, "javascript: image URL rejected")

        # cleanup: release any slots still held by the smoke patient
        for appt in (await c.get("/appointments/me", headers=patient)).json():
            if appt["status"] in ("PENDING", "CONFIRMED"):
                await c.patch(f"/appointments/{appt['id']}/status", headers=patient, json={"status": "CANCELLED"})

    await delete_test_users()
    failed = [label for ok, label in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    sys.exit(1 if failed else 0)


asyncio.run(main())
