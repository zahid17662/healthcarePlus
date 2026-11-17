import { useState } from 'react';
import { api } from '@/api';
import type { Appointment, AppointmentStatus } from '@/types';
import { useToast } from '@/context/ToastContext';
import { formatTime12, todayISO } from '@/lib/date';
import { getErrorMessage } from '@/lib/errors';
import { useAsync } from '@/lib/hooks';
import { Button, Card, EmptyState, Input, Select, Spinner, StatusBadge } from '@/components/ui';

const STATUSES: AppointmentStatus[] = ['pending', 'confirmed', 'completed', 'cancelled'];

/** Must match the backend's allowed transitions. */
const NEXT_STATUSES: Record<AppointmentStatus, AppointmentStatus[]> = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['completed', 'cancelled'],
  completed: [],
  cancelled: [],
};

const ACTION_LABEL: Record<AppointmentStatus, string> = {
  pending: 'Mark pending',
  confirmed: 'Confirm',
  completed: 'Complete',
  cancelled: 'Cancel',
};

export function AdminAppointments() {
  const { notify } = useToast();
  const [date, setDate] = useState(todayISO);
  const [status, setStatus] = useState<AppointmentStatus | ''>('');
  const [doctorId, setDoctorId] = useState('');
  const [busyId, setBusyId] = useState<string | null>(null);

  const doctors = useAsync(() => api.admin.doctors(), []);
  const appointments = useAsync(() => api.admin.appointments({ date, status, doctorId: doctorId || undefined }), [date, status, doctorId]);

  const changeStatus = async (appt: Appointment, next: AppointmentStatus): Promise<void> => {
    setBusyId(appt.id);
    try {
      await api.admin.updateStatus(appt.id, next);
      notify('success', `Appointment ${next}`, `${appt.patientName} · ${formatTime12(appt.startTime)}`);
      appointments.reload();
    } catch (err) {
      notify('error', 'Status update failed', getErrorMessage(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="grid gap-3 p-4 sm:grid-cols-3">
        <label className="text-sm text-slate-600 dark:text-slate-300">
          Date
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="mt-1" />
        </label>
        <label className="text-sm text-slate-600 dark:text-slate-300">
          Status
          <Select value={status} onChange={(e) => setStatus(e.target.value as AppointmentStatus | '')} className="mt-1">
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s} className="capitalize">
                {s}
              </option>
            ))}
          </Select>
        </label>
        <label className="text-sm text-slate-600 dark:text-slate-300">
          Doctor
          <Select value={doctorId} onChange={(e) => setDoctorId(e.target.value)} className="mt-1">
            <option value="">All doctors</option>
            {(doctors.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </Select>
        </label>
      </Card>

      {appointments.isLoading && !appointments.data ? (
        <Spinner />
      ) : appointments.error ? (
        <EmptyState title="Couldn't load appointments" description={appointments.error} action={<Button onClick={appointments.reload}>Retry</Button>} />
      ) : !appointments.data?.length ? (
        <EmptyState title="No appointments" description="Nothing matches these filters." />
      ) : (
        <Card className="overflow-x-auto p-0">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800">
              <tr>
                <th className="px-4 py-3 font-medium">Time</th>
                <th className="px-4 py-3 font-medium">Patient</th>
                <th className="px-4 py-3 font-medium">Doctor</th>
                <th className="px-4 py-3 font-medium">Concerns</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {appointments.data.map((a) => (
                <tr key={a.id} className="align-top">
                  <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900 dark:text-white">
                    {formatTime12(a.startTime)}
                    <span className="block text-xs font-normal text-slate-500">{a.date}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-700 dark:text-slate-200">{a.patientName}</td>
                  <td className="px-4 py-3 text-slate-700 dark:text-slate-200">
                    {a.doctorName}
                    <span className="block text-xs text-slate-500">{a.specialization}</span>
                  </td>
                  <td className="max-w-xs px-4 py-3 text-slate-600 dark:text-slate-300">
                    <span className="line-clamp-2">{a.concerns || '—'}</span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-2">
                      {NEXT_STATUSES[a.status].map((next) => (
                        <Button
                          key={next}
                          size="sm"
                          variant={next === 'cancelled' ? 'secondary' : 'primary'}
                          isLoading={busyId === a.id}
                          onClick={() => changeStatus(a, next)}
                        >
                          {ACTION_LABEL[next]}
                        </Button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
