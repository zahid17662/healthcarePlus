# MediBook — Backend

FastAPI + SQLAlchemy (async) + PostgreSQL (Neon). Three layers: **routers** (HTTP) → **services**
(business rules) → **repositories** (SQL).

## Run

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
cp .env.example .env                              # then fill DATABASE_URL and JWT_SECRET
.venv/Scripts/python scripts/migrate.py           # create tables (idempotent)
.venv/Scripts/python scripts/seed.py              # admin + 8 sample doctors (idempotent)
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs · health: `/health`

`seed.py` writes a random admin password to `backend/.admin-credentials.txt` (git-ignored, never
printed). Set `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` to choose your own. Delete the sample
doctors from the admin UI (or skip seeding) before real use.

## Tests

```bash
.venv/Scripts/pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest                            # everything
.venv/Scripts/python -m pytest -m unit                    # fast, no database
.venv/Scripts/python -m pytest -m integration             # API + database
.venv/Scripts/python -m pytest --cov=app --cov-report=term-missing --cov-report=html   # coverage (gate: 80%)
```

- `tests/unit` — slot generation, status transitions, JWT/password handling, config, schemas, rate limiter.
  No database needed.
- `tests/integration` — the real FastAPI app called in-process: auth, doctors, availability, booking,
  the double-booking race (8 concurrent patients, exactly one 201), cancel and rebook, notifications,
  recommendations, admin routes, statistics, and a 401/403 matrix over every endpoint.

**Test database safety.** Tests never touch production data. Every connection is pinned to a separate
Postgres schema (`medibook_test`, override with `TEST_DB_SCHEMA`), which is recreated from `sql/*.sql` at the
start of a run and dropped at the end. Before any test executes, the suite checks through the application's
own engine that it really is on that schema and aborts otherwise. It reads the database from
`TEST_DATABASE_URL`, falling back to `DATABASE_URL` in `.env`; use a direct (non `-pooler`) endpoint, or
point `TEST_DATABASE_URL` at a throw-away Postgres in CI. Without any database, only unit tests run.

## Double-booking guard

`sql/001_schema.sql` defines the partial unique index from the design:

```sql
CREATE UNIQUE INDEX idx_unique_active_doctor_slot
  ON appointments (doctor_id, appointment_date, start_time) WHERE status != 'CANCELLED';
```

`services/booking.py` validates first (friendly errors, fast path) but the index is the real lock:
concurrent inserts for one slot → one commits, the rest get `IntegrityError` → **HTTP 409**.
Cancelling frees the slot without deleting history.

## API (`/api/v1`)

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/auth/register` · `/auth/login` | public (rate-limited) | accounts, JWT |
| GET | `/auth/me` · PATCH `/users/me` | any | profile |
| GET | `/doctors?q=&specialization=` · `/doctors/specializations` · `/doctors/{id}` · `/doctors/{id}/reviews` | any | directory |
| GET | `/doctors/{id}/slots?date=` | any | open / booked / blocked / past slots |
| GET | `/recommendations?doctorId=&date=` | any | same-specialty alternatives, earliest slot then rating |
| POST | `/appointments` | patient | atomic booking, 409 on conflict |
| GET | `/appointments/me` | patient | my bookings |
| PATCH | `/appointments/{id}/status` | patient (cancel own) · admin (transitions) | lifecycle |
| GET · POST | `/notifications` · `/notifications/read-all` | any | in-app notifications |
| GET | `/admin/appointments?date=&status=&doctorId=` | admin | all bookings |
| GET · POST · PUT | `/admin/doctors` · `/admin/doctors/{id}` | admin | doctor management |
| GET · PUT | `/admin/doctors/{id}/schedule` | admin | hours, slot length, break, blocked dates |
| GET | `/admin/stats/daily?date=` | admin | single-pass aggregate stats |

Status lifecycle: `PENDING → CONFIRMED → COMPLETED`, and `PENDING/CONFIRMED → CANCELLED`.

## Notes

- **Database endpoint:** use Neon's *direct* host (no `-pooler`). Through PgBouncer asyncpg can't cache
  prepared statements and queries were 3–10× slower. `app/db.py` switches modes automatically.
- **Timezone:** "past slot" decisions use `CLINIC_TIMEZONE` (default `Asia/Dhaka`).
- **Rate limiting** on login/register is in-memory (per process); use a shared store when scaling out.
- **Schedule edits** regenerate future slot offers; existing bookings are left untouched.
- JSON is camelCase to match the TypeScript client; enums are UPPERCASE on the wire.
