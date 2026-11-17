import type {
  Appointment,
  AppointmentStatus,
  DailyStats,
  Doctor,
  DoctorInput,
  DoctorSchedule,
  Notification,
  Recommendation,
  User,
} from '@/types';
import { ApiError, SLOT_CONFLICT } from '@/lib/errors';
import { addDays, minutesToTime, timeToMinutes, todayISO } from '@/lib/date';
import { buildAvailability, slotKey } from '@/lib/slots';
import type { HealthcareApi } from './types';
import { hashPassword, initDb, readDb, writeDb, type MockDb, type StoredUser } from './mockDb';
import { tokenStore } from './tokenStore';

const LATENCY_MS = 250;
const RECOMMENDATION_LOOKAHEAD_DAYS = 14;
const MAX_RECOMMENDATIONS = 3;
const MAX_CONCERNS_LENGTH = 1000;
const TOKEN_PREFIX = 'mock-token.';

/** Allowed lifecycle transitions (PRD: Pending → Confirmed → Completed, or Cancelled). */
export const STATUS_TRANSITIONS: Record<AppointmentStatus, AppointmentStatus[]> = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['completed', 'cancelled'],
  completed: [],
  cancelled: [],
};

const delay = (ms = LATENCY_MS): Promise<void> => new Promise((r) => setTimeout(r, ms));
const uid = (prefix: string): string => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
const now = (): string => new Date().toISOString();

async function db(): Promise<MockDb> {
  await delay();
  // Re-read on every call so concurrent tabs see each other's writes.
  return readDb() ?? initDb();
}

function publicUser({ passwordHash: _omit, ...user }: StoredUser): User {
  return user;
}

function currentUser(state: MockDb): StoredUser {
  const token = tokenStore.get();
  const id = token?.startsWith(TOKEN_PREFIX) ? token.slice(TOKEN_PREFIX.length) : null;
  const user = state.users.find((u) => u.id === id);
  if (!user) throw new ApiError('Your session has expired. Please sign in again.', 401);
  return user;
}

function requireAdmin(state: MockDb): StoredUser {
  const user = currentUser(state);
  if (user.role !== 'admin') throw new ApiError('Administrator access required.', 403);
  return user;
}

function withRating(doctor: Doctor, state: MockDb): Doctor {
  const reviews = state.reviews.filter((r) => r.doctorId === doctor.id);
  if (reviews.length === 0) return { ...doctor, averageRating: 0, reviewCount: 0 };
  const avg = reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length;
  return { ...doctor, averageRating: Math.round(avg * 10) / 10, reviewCount: reviews.length };
}

function findDoctor(state: MockDb, id: string): Doctor {
  const doctor = state.doctors.find((d) => d.id === id);
  if (!doctor) throw new ApiError('Doctor not found.', 404);
  return withRating(doctor, state);
}

function findSchedule(state: MockDb, doctorId: string): DoctorSchedule {
  const schedule = state.schedules.find((s) => s.doctorId === doctorId);
  if (!schedule) throw new ApiError('Schedule not found.', 404);
  return schedule;
}

function notify(userId: string, title: string, message: string): Notification {
  return { id: uid('n'), userId, title, message, read: false, createdAt: now() };
}

function validateEmail(email: string): string {
  const clean = email.trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(clean)) throw new ApiError('Enter a valid email address.', 422);
  return clean;
}

function earliestOpenSlot(state: MockDb, doctor: Doctor, fromDate: string): Recommendation | null {
  const schedule = state.schedules.find((s) => s.doctorId === doctor.id);
  if (!schedule) return null;
  for (let i = 0; i <= RECOMMENDATION_LOOKAHEAD_DAYS; i += 1) {
    const date = addDays(fromDate, i);
    const day = buildAvailability({ schedule, date, appointments: state.appointments });
    const open = day.slots.find((s) => s.status === 'available');
    if (open) return { doctor, date, startTime: open.startTime };
  }
  return null;
}

function buildStats(state: MockDb, date: string): DailyStats {
  const onDay = state.appointments.filter((a) => a.date === date);
  const count = (s: AppointmentStatus): number => onDay.filter((a) => a.status === s).length;
  const specialtyCounts = onDay
    .filter((a) => a.status !== 'cancelled')
    .reduce<Record<string, number>>((acc, a) => ({ ...acc, [a.specialization]: (acc[a.specialization] ?? 0) + 1 }), {});
  const activeDoctors = state.doctors.filter((d) => {
    const s = state.schedules.find((x) => x.doctorId === d.id);
    return d.isActive && s && buildAvailability({ schedule: s, date, appointments: [] }).isWorkingDay;
  }).length;
  const last7Days = Array.from({ length: 7 }, (_, i) => {
    const d = addDays(date, i - 6);
    const list = state.appointments.filter((a) => a.date === d);
    return { date: d, bookings: list.length, cancelled: list.filter((a) => a.status === 'cancelled').length };
  });
  return {
    date,
    totalBookings: onDay.length,
    confirmed: count('confirmed'),
    pending: count('pending'),
    completed: count('completed'),
    cancelled: count('cancelled'),
    cancellationRate: onDay.length ? count('cancelled') / onDay.length : 0,
    activeDoctors,
    bySpecialty: Object.entries(specialtyCounts)
      .map(([specialization, c]) => ({ specialization, count: c }))
      .sort((a, b) => b.count - a.count),
    last7Days,
  };
}

function updateAppointment(state: MockDb, id: string, status: AppointmentStatus, actor: string): { next: MockDb; updated: Appointment } {
  const appt = state.appointments.find((a) => a.id === id);
  if (!appt) throw new ApiError('Appointment not found.', 404);
  if (!STATUS_TRANSITIONS[appt.status].includes(status)) {
    throw new ApiError(`Cannot change a ${appt.status} appointment to ${status}.`, 409);
  }
  const updated: Appointment = { ...appt, status, updatedAt: now() };
  const message = `${appt.doctorName} · ${appt.date} ${appt.startTime} is now ${status} (${actor}).`;
  const next: MockDb = {
    ...state,
    appointments: state.appointments.map((a) => (a.id === id ? updated : a)),
    notifications: [notify(appt.patientId, `Appointment ${status}`, message), ...state.notifications],
  };
  return { next, updated };
}

export function createMockApi(): HealthcareApi {
  return {
    auth: {
      async login({ email, password }) {
        const state = await db();
        const clean = validateEmail(email);
        const user = state.users.find((u) => u.email === clean);
        if (!user || user.passwordHash !== (await hashPassword(password))) {
          throw new ApiError('Incorrect email or password.', 401);
        }
        return { token: `${TOKEN_PREFIX}${user.id}`, user: publicUser(user) };
      },
      async register({ fullName, email, password }) {
        const state = await db();
        const clean = validateEmail(email);
        if (fullName.trim().length < 2) throw new ApiError('Enter your full name.', 422);
        if (password.length < 8) throw new ApiError('Password must be at least 8 characters.', 422);
        if (state.users.some((u) => u.email === clean)) throw new ApiError('An account with this email already exists.', 409);
        const user: StoredUser = {
          id: uid('u'),
          fullName: fullName.trim(),
          email: clean,
          role: 'patient',
          createdAt: now(),
          passwordHash: await hashPassword(password),
        };
        writeDb({ ...state, users: [...state.users, user] });
        return { token: `${TOKEN_PREFIX}${user.id}`, user: publicUser(user) };
      },
      async me() {
        return publicUser(currentUser(await db()));
      },
      async updateProfile(update) {
        const state = await db();
        const user = currentUser(state);
        if (update.fullName !== undefined && update.fullName.trim().length < 2) {
          throw new ApiError('Enter your full name.', 422);
        }
        const updated: StoredUser = { ...user, ...update, fullName: update.fullName?.trim() ?? user.fullName };
        writeDb({ ...state, users: state.users.map((u) => (u.id === user.id ? updated : u)) });
        return publicUser(updated);
      },
    },

    doctors: {
      async list(query = {}) {
        const state = await db();
        const q = query.q?.trim().toLowerCase() ?? '';
        return state.doctors
          .filter((d) => d.isActive)
          .filter((d) => !query.specialization || d.specialization === query.specialization)
          .filter(
            (d) =>
              !q ||
              d.name.toLowerCase().includes(q) ||
              d.specialization.toLowerCase().includes(q) ||
              d.subSpecialties.some((s) => s.toLowerCase().includes(q)),
          )
          .map((d) => withRating(d, state));
      },
      async get(id) {
        return findDoctor(await db(), id);
      },
      async specializations() {
        const state = await db();
        return [...new Set(state.doctors.filter((d) => d.isActive).map((d) => d.specialization))].sort();
      },
      async reviews(id) {
        const state = await db();
        return state.reviews.filter((r) => r.doctorId === id).sort((a, b) => b.createdAt.localeCompare(a.createdAt));
      },
      async availability(id, date) {
        const state = await db();
        findDoctor(state, id);
        return buildAvailability({ schedule: findSchedule(state, id), date, appointments: state.appointments });
      },
      async recommendations(id, date) {
        const state = await db();
        const doctor = findDoctor(state, id);
        return state.doctors
          .filter((d) => d.isActive && d.id !== id && d.specialization === doctor.specialization)
          .map((d) => earliestOpenSlot(state, withRating(d, state), date))
          .filter((r): r is Recommendation => r !== null)
          .sort(
            (a, b) =>
              `${a.date} ${a.startTime}`.localeCompare(`${b.date} ${b.startTime}`) ||
              b.doctor.averageRating - a.doctor.averageRating,
          )
          .slice(0, MAX_RECOMMENDATIONS);
      },
    },

    appointments: {
      async book({ doctorId, date, startTime, concerns }) {
        const state = await db();
        const patient = currentUser(state);
        if (patient.role !== 'patient') throw new ApiError('Only patients can book appointments.', 403);
        if (date < todayISO()) throw new ApiError('Choose a date in the future.', 422);
        if (concerns.length > MAX_CONCERNS_LENGTH) throw new ApiError('Concerns note is too long.', 422);

        const doctor = findDoctor(state, doctorId);
        const schedule = findSchedule(state, doctorId);
        const day = buildAvailability({ schedule, date, appointments: state.appointments });
        const slot = day.slots.find((s) => s.startTime === startTime);
        if (!slot || slot.status === 'blocked' || slot.status === 'past') {
          throw new ApiError('This time slot is not available.', 422);
        }

        // Composite unique constraint: (doctor_id, date, start_time) among active bookings.
        const active = state.appointments.filter((a) => a.status !== 'cancelled');
        const taken = new Set(active.map((a) => slotKey(a.doctorId, a.date, a.startTime)));
        if (slot.status === 'booked' || taken.has(slotKey(doctorId, date, startTime))) {
          throw new ApiError('Sorry, this slot was just booked by another patient.', SLOT_CONFLICT);
        }
        if (active.some((a) => a.patientId === patient.id && a.date === date && a.startTime === startTime)) {
          throw new ApiError('You already have another appointment at this time.', SLOT_CONFLICT);
        }

        const appointment: Appointment = {
          id: uid('a'),
          patientId: patient.id,
          patientName: patient.fullName,
          doctorId,
          doctorName: doctor.name,
          specialization: doctor.specialization,
          date,
          startTime,
          endTime: minutesToTime(timeToMinutes(startTime) + schedule.slotMinutes),
          concerns: concerns.trim(),
          status: 'confirmed',
          createdAt: now(),
          updatedAt: now(),
        };
        const confirmation = notify(
          patient.id,
          'Appointment confirmed',
          `Your visit with ${doctor.name} on ${date} at ${startTime} is locked in.`,
        );
        writeDb({
          ...state,
          appointments: [...state.appointments, appointment],
          notifications: [confirmation, ...state.notifications],
        });
        return appointment;
      },
      async mine() {
        const state = await db();
        const user = currentUser(state);
        return state.appointments
          .filter((a) => a.patientId === user.id)
          .sort((a, b) => `${b.date}${b.startTime}`.localeCompare(`${a.date}${a.startTime}`));
      },
      async cancel(id) {
        const state = await db();
        const user = currentUser(state);
        const appt = state.appointments.find((a) => a.id === id);
        if (!appt || appt.patientId !== user.id) throw new ApiError('Appointment not found.', 404);
        if (appt.date < todayISO()) throw new ApiError('Past appointments cannot be cancelled.', 422);
        const { next, updated } = updateAppointment(state, id, 'cancelled', 'by you');
        writeDb(next);
        return updated;
      },
    },

    notifications: {
      async list() {
        const state = await db();
        const user = currentUser(state);
        return state.notifications.filter((n) => n.userId === user.id).slice(0, 20);
      },
      async markAllRead() {
        const state = await db();
        const user = currentUser(state);
        writeDb({
          ...state,
          notifications: state.notifications.map((n) => (n.userId === user.id ? { ...n, read: true } : n)),
        });
      },
    },

    admin: {
      async appointments(query = {}) {
        const state = await db();
        requireAdmin(state);
        return state.appointments
          .filter((a) => !query.date || a.date === query.date)
          .filter((a) => !query.status || a.status === query.status)
          .filter((a) => !query.doctorId || a.doctorId === query.doctorId)
          .sort((a, b) => `${a.date}${a.startTime}`.localeCompare(`${b.date}${b.startTime}`));
      },
      async updateStatus(id, status) {
        const state = await db();
        requireAdmin(state);
        const { next, updated } = updateAppointment(state, id, status, 'by the hospital');
        writeDb(next);
        return updated;
      },
      async doctors() {
        const state = await db();
        requireAdmin(state);
        return state.doctors.map((d) => withRating(d, state));
      },
      async createDoctor(input) {
        const state = await db();
        requireAdmin(state);
        const doctor: Doctor = { ...validateDoctor(input), id: uid('d'), averageRating: 0, reviewCount: 0 };
        const schedule: DoctorSchedule = {
          doctorId: doctor.id,
          workingDays: [0, 1, 2, 3, 4],
          startTime: '09:00',
          endTime: '17:00',
          slotMinutes: 30,
          breakStart: '13:00',
          breakEnd: '14:00',
          blockedDates: [],
        };
        writeDb({ ...state, doctors: [...state.doctors, doctor], schedules: [...state.schedules, schedule] });
        return doctor;
      },
      async updateDoctor(id, input) {
        const state = await db();
        requireAdmin(state);
        const existing = findDoctor(state, id);
        const updated: Doctor = { ...existing, ...validateDoctor(input) };
        writeDb({ ...state, doctors: state.doctors.map((d) => (d.id === id ? updated : d)) });
        return updated;
      },
      async getSchedule(doctorId) {
        const state = await db();
        requireAdmin(state);
        return findSchedule(state, doctorId);
      },
      async updateSchedule(schedule) {
        const state = await db();
        requireAdmin(state);
        validateSchedule(schedule);
        writeDb({ ...state, schedules: state.schedules.map((s) => (s.doctorId === schedule.doctorId ? schedule : s)) });
        return schedule;
      },
      async stats(date) {
        const state = await db();
        requireAdmin(state);
        return buildStats(state, date);
      },
    },
  };
}

function validateDoctor(input: DoctorInput): DoctorInput {
  if (input.name.trim().length < 3) throw new ApiError('Doctor name is required.', 422);
  if (!input.specialization.trim()) throw new ApiError('Specialization is required.', 422);
  if (!(input.hourlyRate > 0)) throw new ApiError('Hourly rate must be greater than 0.', 422);
  if (input.experienceYears < 0) throw new ApiError('Experience cannot be negative.', 422);
  return { ...input, name: input.name.trim(), specialization: input.specialization.trim() };
}

function validateSchedule(s: DoctorSchedule): void {
  const start = timeToMinutes(s.startTime);
  const end = timeToMinutes(s.endTime);
  if (end <= start) throw new ApiError('End time must be after start time.', 422);
  if (s.slotMinutes < 10 || s.slotMinutes > 120) throw new ApiError('Slot length must be 10–120 minutes.', 422);
  if (s.breakStart && s.breakEnd && timeToMinutes(s.breakEnd) <= timeToMinutes(s.breakStart)) {
    throw new ApiError('Break end must be after break start.', 422);
  }
}
