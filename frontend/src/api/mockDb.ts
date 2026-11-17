import type { Appointment, AppointmentStatus, Doctor, DoctorSchedule, Notification, Review, User } from '@/types';
import { DEMO_ACCOUNTS, SEED_DOCTORS, SEED_REVIEWS, SEED_SCHEDULES } from '@/data/seed';
import { addDays, minutesToTime, timeToMinutes, todayISO } from '@/lib/date';
import { buildAvailability } from '@/lib/slots';

export interface StoredUser extends User {
  passwordHash: string;
}

export interface MockDb {
  version: 1;
  users: StoredUser[];
  doctors: Doctor[];
  schedules: DoctorSchedule[];
  appointments: Appointment[];
  reviews: Review[];
  notifications: Notification[];
}

const DB_KEY = 'medibook.mockdb.v1';
let memoryDb: MockDb | null = null;

export async function hashPassword(password: string): Promise<string> {
  const data = new TextEncoder().encode(`medibook:${password}`);
  if (globalThis.crypto?.subtle) {
    const digest = await crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('');
  }
  // Non-secure context fallback (mock only): FNV-1a.
  let h = 0x811c9dc5;
  data.forEach((b) => {
    h = Math.imul(h ^ b, 0x01000193) >>> 0;
  });
  return h.toString(16);
}

export function readDb(): MockDb | null {
  try {
    const raw = localStorage.getItem(DB_KEY);
    return raw ? (JSON.parse(raw) as MockDb) : memoryDb;
  } catch {
    return memoryDb;
  }
}

export function writeDb(db: MockDb): void {
  memoryDb = db;
  try {
    localStorage.setItem(DB_KEY, JSON.stringify(db));
  } catch {
    /* quota / private mode — keep in memory */
  }
}

const FAKE_PATIENTS = ['Rahim U.', 'Sumaiya K.', 'Jahid H.', 'Mehnaz T.', 'Ovi R.', 'Priya S.', 'Karim B.'];
const SAMPLE_CONCERNS = [
  'Recurring headache for two weeks, worse in the morning.',
  'Chest tightness when climbing stairs.',
  'Itchy rash on both arms.',
  'Follow-up on blood test results.',
  'Knee pain after running.',
  'Child has had a fever for three days.',
];

function seedAppointments(): Appointment[] {
  const today = todayISO();
  const result: Appointment[] = [];
  for (let offset = -6; offset <= 4; offset += 1) {
    const date = addDays(today, offset);
    SEED_SCHEDULES.forEach((schedule, di) => {
      const day = buildAvailability({ schedule, date, appointments: [], now: new Date(0) });
      day.slots
        .filter((s) => s.status !== 'blocked')
        .filter((_, si) => (si + di + offset + 20) % 4 === 0)
        .forEach((slot, k) => {
          const doctor = SEED_DOCTORS[di];
          const isPast = offset < 0;
          const seq = result.length;
          const status: AppointmentStatus = isPast
            ? seq % 6 === 0 ? 'cancelled' : 'completed'
            : seq % 5 === 0 ? 'pending' : 'confirmed';
          const isDemo = seq % 9 === 0;
          const createdAt = new Date(Date.now() - (7 - offset) * 86_400_000).toISOString();
          result.push({
            id: `a-seed-${seq}`,
            patientId: isDemo ? 'u-patient' : `p-${k}`,
            patientName: isDemo ? 'Demo Patient' : FAKE_PATIENTS[seq % FAKE_PATIENTS.length],
            doctorId: doctor.id,
            doctorName: doctor.name,
            specialization: doctor.specialization,
            date,
            startTime: slot.startTime,
            endTime: minutesToTime(timeToMinutes(slot.startTime) + schedule.slotMinutes),
            concerns: SAMPLE_CONCERNS[seq % SAMPLE_CONCERNS.length],
            status,
            createdAt,
            updatedAt: createdAt,
          });
        });
    });
  }
  return result;
}

export async function initDb(): Promise<MockDb> {
  const existing = readDb();
  if (existing) return existing;
  const users = await Promise.all(
    DEMO_ACCOUNTS.map(async ({ password, ...u }) => ({
      ...u,
      createdAt: new Date().toISOString(),
      passwordHash: await hashPassword(password),
    })),
  );
  const db: MockDb = {
    version: 1,
    users,
    doctors: SEED_DOCTORS,
    schedules: SEED_SCHEDULES,
    appointments: seedAppointments(),
    reviews: SEED_REVIEWS,
    notifications: [],
  };
  writeDb(db);
  return db;
}
