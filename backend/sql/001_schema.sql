-- MediBook schema (PostgreSQL). Idempotent: safe to re-run.

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('PATIENT', 'ADMIN');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE appt_status AS ENUM ('PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name     VARCHAR(120) NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          user_role NOT NULL DEFAULT 'PATIENT',
    phone         VARCHAR(32),
    date_of_birth DATE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS doctors (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name        VARCHAR(120) NOT NULL,
    specialization   VARCHAR(80) NOT NULL,
    hourly_rate      NUMERIC(8, 2) NOT NULL CHECK (hourly_rate > 0),
    experience_years SMALLINT NOT NULL DEFAULT 0 CHECK (experience_years >= 0),
    experience_bio   TEXT NOT NULL DEFAULT '',
    sub_specialties  TEXT[] NOT NULL DEFAULT '{}',
    avatar_url       TEXT,
    rating_avg       NUMERIC(3, 2) NOT NULL DEFAULT 0.00,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_doctors_specialization ON doctors (specialization);

-- Materialised bookable slots (one row per weekday + start time), generated from the config below.
CREATE TABLE IF NOT EXISTS doctor_schedules (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id    UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    day_of_week  SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),  -- 0 = Sunday
    slot_time    TIME NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (doctor_id, day_of_week, slot_time)
);

-- What the admin edits: hours, slot length, break. Slots above are regenerated from this.
CREATE TABLE IF NOT EXISTS doctor_schedule_configs (
    doctor_id    UUID PRIMARY KEY REFERENCES doctors(id) ON DELETE CASCADE,
    working_days SMALLINT[] NOT NULL DEFAULT '{1,2,3,4,5}',
    start_time   TIME NOT NULL DEFAULT '09:00',
    end_time     TIME NOT NULL DEFAULT '17:00',
    slot_minutes SMALLINT NOT NULL DEFAULT 30 CHECK (slot_minutes BETWEEN 10 AND 120),
    break_start  TIME,
    break_end    TIME,
    CHECK (end_time > start_time)
);

CREATE TABLE IF NOT EXISTS doctor_blocked_dates (
    doctor_id    UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    blocked_date DATE NOT NULL,
    PRIMARY KEY (doctor_id, blocked_date)
);

CREATE TABLE IF NOT EXISTS appointments (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doctor_id        UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    appointment_date DATE NOT NULL,
    start_time       TIME NOT NULL,
    end_time         TIME NOT NULL,
    patient_concerns TEXT,
    symptoms         TEXT[] NOT NULL DEFAULT '{}',
    status           appt_status NOT NULL DEFAULT 'PENDING',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Critical concurrency guard: no double-booking unless the earlier booking was cancelled.
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_doctor_slot
    ON appointments (doctor_id, appointment_date, start_time)
    WHERE status != 'CANCELLED';

CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments (patient_id, appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments (appointment_date);

CREATE TABLE IF NOT EXISTS reviews (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doctor_id    UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    patient_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    patient_name VARCHAR(120) NOT NULL,
    rating       SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment      TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reviews_doctor ON reviews (doctor_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      VARCHAR(160) NOT NULL,
    message    TEXT NOT NULL,
    is_read    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, created_at DESC);
