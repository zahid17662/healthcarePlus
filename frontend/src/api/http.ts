import type { Appointment, AppointmentStatus, AuthSession, Role, User } from '@/types';
import { ApiError } from '@/lib/errors';
import type { HealthcareApi } from './types';
import { tokenStore } from './tokenStore';

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/** The FastAPI service version-prefixes every route. */
const API_PREFIX = '/api/v1';

/* ---------- wire format: the API uses UPPERCASE enums, the UI uses lowercase ---------- */

type WireStatus = Uppercase<AppointmentStatus>;
type WireRole = Uppercase<Role>;
type WireUser = Omit<User, 'role'> & { role: WireRole };
type WireAppointment = Omit<Appointment, 'status'> & { status: WireStatus };
type WireSession = Omit<AuthSession, 'user'> & { user: WireUser };

const fromWireUser = (u: WireUser): User => ({ ...u, role: u.role.toLowerCase() as Role });
const fromWireAppointment = (a: WireAppointment): Appointment => ({ ...a, status: a.status.toLowerCase() as AppointmentStatus });
const fromWireSession = (s: WireSession): AuthSession => ({ ...s, user: fromWireUser(s.user) });
const toWireStatus = (s: AppointmentStatus): WireStatus => s.toUpperCase() as WireStatus;

function toQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v) search.set(k, v);
  });
  const s = search.toString();
  return s ? `?${s}` : '';
}

/** FastAPI errors look like `{ "detail": "message" }`. */
function errorMessage(payload: unknown, status: number): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const { detail } = payload as { detail: unknown };
    if (typeof detail === 'string') return detail;
  }
  return `Request failed (${status})`;
}

export function createHttpApi(baseUrl: string): HealthcareApi {
  const root = `${baseUrl.replace(/\/$/, '')}${API_PREFIX}`;

  async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
    const token = tokenStore.get();
    let res: Response;
    try {
      res = await fetch(`${root}${path}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError('Cannot reach the server. Check your connection.', 0);
    }

    const payload: unknown = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) throw new ApiError(errorMessage(payload, res.status), res.status);
    return payload as T;
  }

  const id = encodeURIComponent;

  return {
    auth: {
      login: async (input) => fromWireSession(await request<WireSession>('POST', '/auth/login', input)),
      register: async (input) => fromWireSession(await request<WireSession>('POST', '/auth/register', input)),
      me: async () => fromWireUser(await request<WireUser>('GET', '/auth/me')),
      updateProfile: async (update) => fromWireUser(await request<WireUser>('PATCH', '/users/me', update)),
    },
    doctors: {
      list: (query = {}) => request('GET', `/doctors${toQuery({ q: query.q, specialization: query.specialization })}`),
      get: (doctorId) => request('GET', `/doctors/${id(doctorId)}`),
      specializations: () => request('GET', '/doctors/specializations'),
      reviews: (doctorId) => request('GET', `/doctors/${id(doctorId)}/reviews`),
      availability: (doctorId, date) => request('GET', `/doctors/${id(doctorId)}/slots${toQuery({ date })}`),
      recommendations: (doctorId, date) => request('GET', `/recommendations${toQuery({ doctorId, date })}`),
    },
    appointments: {
      book: async (req) => fromWireAppointment(await request<WireAppointment>('POST', '/appointments', req)),
      mine: async () => (await request<WireAppointment[]>('GET', '/appointments/me')).map(fromWireAppointment),
      cancel: async (apptId) =>
        fromWireAppointment(
          await request<WireAppointment>('PATCH', `/appointments/${id(apptId)}/status`, { status: toWireStatus('cancelled') }),
        ),
    },
    notifications: {
      list: () => request('GET', '/notifications'),
      markAllRead: () => request('POST', '/notifications/read-all'),
    },
    admin: {
      appointments: async (q = {}) =>
        (
          await request<WireAppointment[]>(
            'GET',
            `/admin/appointments${toQuery({ date: q.date, status: q.status ? toWireStatus(q.status) : undefined, doctorId: q.doctorId })}`,
          )
        ).map(fromWireAppointment),
      updateStatus: async (apptId, status) =>
        fromWireAppointment(
          await request<WireAppointment>('PATCH', `/appointments/${id(apptId)}/status`, { status: toWireStatus(status) }),
        ),
      doctors: () => request('GET', '/admin/doctors'),
      createDoctor: (input) => request('POST', '/admin/doctors', input),
      updateDoctor: (doctorId, input) => request('PUT', `/admin/doctors/${id(doctorId)}`, input),
      getSchedule: (doctorId) => request('GET', `/admin/doctors/${id(doctorId)}/schedule`),
      updateSchedule: (s) => request('PUT', `/admin/doctors/${id(s.doctorId)}/schedule`, s),
      stats: (date) => request('GET', `/admin/stats/daily${toQuery({ date })}`),
    },
  };
}
