"""Seed an admin account plus sample doctors/schedules/reviews. Safe to re-run (skips existing data).

Admin email:    SEED_ADMIN_EMAIL    (default admin@medibook.local)
Admin password: SEED_ADMIN_PASSWORD (default: random; written to backend/.admin-credentials.txt, never printed)
"""
import asyncio
import os
import secrets
import sys
from datetime import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.db import SessionFactory, engine  # noqa: E402
from app.models import Doctor, DoctorScheduleConfig, Review, User, UserRole  # noqa: E402
from app.repositories import doctors as doctors_repo  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.admin import generate_slots  # noqa: E402

CREDENTIALS_FILE = ROOT / ".admin-credentials.txt"


def portrait(gender: str, n: int) -> str:
    return f"https://randomuser.me/api/portraits/{gender}/{n}.jpg"


# (name, specialization, sub-specialties, years, rate, image, bio)
DOCTORS = [
    ("Dr. Sarah Ahmed", "Cardiology", ["Heart failure", "Hypertension", "Echocardiography"], 14, 120, portrait("women", 44),
     "Consultant cardiologist focused on preventive cardiology and long-term heart failure management."),
    ("Dr. Imran Hossain", "Cardiology", ["Arrhythmia", "Pacemakers", "Chest pain clinic"], 9, 95, portrait("men", 32),
     "Electrophysiology-trained cardiologist treating palpitations, arrhythmias and device follow-ups."),
    ("Dr. Nadia Rahman", "Dermatology", ["Acne", "Eczema", "Cosmetic dermatology"], 11, 80, portrait("women", 65),
     "Treats chronic skin conditions with an evidence-based, patient-friendly approach."),
    ("Dr. Arif Chowdhury", "Neurology", ["Migraine", "Epilepsy", "Stroke rehab"], 17, 140, portrait("men", 52),
     "Senior neurologist with a special interest in headache disorders and seizure management."),
    ("Dr. Farhana Kabir", "Pediatrics", ["Newborn care", "Vaccination", "Childhood asthma"], 8, 70, portrait("women", 26),
     "Gentle, family-centred paediatric care from newborns to teenagers."),
    ("Dr. Tanvir Alam", "Orthopedics", ["Sports injuries", "Knee & hip", "Arthroscopy"], 12, 110, portrait("men", 41),
     "Orthopaedic surgeon helping patients return to activity after joint and sports injuries."),
    ("Dr. Mahmud Karim", "General Medicine", ["Diabetes", "Fever clinic", "Health check-ups"], 6, 50, portrait("men", 75),
     "Primary-care physician for everyday illnesses, chronic disease follow-up and annual check-ups."),
    ("Dr. Lamia Sultana", "Dermatology", ["Psoriasis", "Hair loss", "Skin allergy"], 7, 65, portrait("women", 12),
     "Dermatologist focused on autoimmune skin disease and hair and scalp disorders."),
]

# doctor index -> [(reviewer, rating, comment)]
REVIEWS = {
    0: [("Rafiq U.", 5, "Explained my echo results clearly and adjusted my meds. Felt genuinely heard."),
        ("Tania M.", 5, "Very thorough and calm. Follow-up plan was easy to understand."),
        ("Kamal H.", 4, "Great doctor, slight wait at the clinic.")],
    1: [("Selina P.", 5, "Finally found the cause of my palpitations."), ("Jamil R.", 4, "Knowledgeable and quick.")],
    2: [("Mitu A.", 5, "My eczema is under control for the first time in years."), ("Sabbir K.", 5, "Friendly, practical advice.")],
    3: [("Nasrin J.", 5, "Migraine plan has cut my attacks in half."), ("Habib S.", 4, "Excellent expertise, busy schedule.")],
    4: [("Ruma D.", 5, "My kids actually like visiting her!"), ("Arman B.", 5, "Patient and reassuring with new parents.")],
    5: [("Fahim Z.", 4, "Back to football after my ACL rehab.")],
    6: [("Shila N.", 4, "Good general check-up, clear diet advice.")],
    7: [("Pinky L.", 5, "Helped a lot with my scalp psoriasis.")],
}

SUNDAY_TO_THURSDAY = [0, 1, 2, 3, 4]
ALTERNATE_DAYS = [1, 3, 5, 6]


async def seed_admin(session) -> None:
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@medibook.local").lower()
    if (await session.execute(select(User).where(User.email == email))).scalar_one_or_none():
        print(f"admin {email}: already exists")
        return
    password = os.environ.get("SEED_ADMIN_PASSWORD") or secrets.token_urlsafe(14)
    session.add(User(full_name="Hospital Admin", email=email, password_hash=await hash_password(password), role=UserRole.ADMIN))
    if "SEED_ADMIN_PASSWORD" not in os.environ:
        CREDENTIALS_FILE.write_text(f"email: {email}\npassword: {password}\n", encoding="utf-8")
        print(f"admin {email}: created (password saved to {CREDENTIALS_FILE.name})")
    else:
        print(f"admin {email}: created (password from SEED_ADMIN_PASSWORD)")


async def seed_doctors(session) -> None:
    if (await session.execute(select(func.count()).select_from(Doctor))).scalar_one() > 0:
        print("doctors: already present, skipping")
        return
    for i, (name, spec, subs, years, rate, image, bio) in enumerate(DOCTORS):
        reviews = REVIEWS.get(i, [])
        average = Decimal(sum(r[1] for r in reviews)) / len(reviews) if reviews else Decimal(0)
        doctor = Doctor(
            full_name=name, specialization=spec, sub_specialties=subs, experience_years=years,
            hourly_rate=Decimal(rate), avatar_url=image, experience_bio=bio,
            rating_avg=average.quantize(Decimal("0.01")),
        )
        session.add(doctor)
        await session.flush()
        days = SUNDAY_TO_THURSDAY if i % 2 == 0 else ALTERNATE_DAYS
        start, end = (time(9), time(17)) if i % 3 == 0 else (time(10), time(16))
        session.add(DoctorScheduleConfig(
            doctor_id=doctor.id, working_days=days, start_time=start, end_time=end,
            slot_minutes=30, break_start=time(13), break_end=time(14),
        ))
        await doctors_repo.replace_slot_rows(session, doctor.id, generate_slots(days, start, end, 30, time(13), time(14)))
        session.add_all(Review(doctor_id=doctor.id, patient_name=who, rating=stars, comment=text) for who, stars, text in reviews)
    print(f"doctors: seeded {len(DOCTORS)} sample doctors with schedules and reviews")


async def main() -> None:
    async with SessionFactory() as session:
        await seed_admin(session)
        await seed_doctors(session)
        await session.commit()
    await engine.dispose()


asyncio.run(main())
