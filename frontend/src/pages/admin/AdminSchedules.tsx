import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { api } from '@/api';
import type { DoctorSchedule, Weekday } from '@/types';
import { useToast } from '@/context/ToastContext';
import { WEEKDAY_LABELS, formatLongDate, todayISO } from '@/lib/date';
import { getErrorMessage } from '@/lib/errors';
import { useAsync } from '@/lib/hooks';
import { cn } from '@/lib/cn';
import { Button, Card, EmptyState, Field, Input, Select, Spinner } from '@/components/ui';

const SLOT_OPTIONS = [15, 20, 30, 45, 60];
const WEEKDAYS: Weekday[] = [0, 1, 2, 3, 4, 5, 6];

export function AdminSchedules() {
  const { notify } = useToast();
  const doctors = useAsync(() => api.admin.doctors(), []);
  const [doctorId, setDoctorId] = useState('');
  const schedule = useAsync(() => api.admin.getSchedule(doctorId), [doctorId], Boolean(doctorId));
  const [draft, setDraft] = useState<DoctorSchedule | null>(null);
  const [blockDate, setBlockDate] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!doctorId && doctors.data?.length) setDoctorId(doctors.data[0].id);
  }, [doctorId, doctors.data]);

  useEffect(() => {
    if (schedule.data && schedule.data.doctorId === doctorId) setDraft(schedule.data);
  }, [schedule.data, doctorId]);

  const patch = (p: Partial<DoctorSchedule>): void => setDraft((d) => (d ? { ...d, ...p } : d));

  const toggleDay = (day: Weekday): void => {
    if (!draft) return;
    const workingDays = draft.workingDays.includes(day)
      ? draft.workingDays.filter((d) => d !== day)
      : [...draft.workingDays, day].sort();
    patch({ workingDays });
  };

  const addBlocked = (): void => {
    if (!draft || !blockDate || draft.blockedDates.includes(blockDate)) return;
    patch({ blockedDates: [...draft.blockedDates, blockDate].sort() });
    setBlockDate('');
  };

  const save = async (): Promise<void> => {
    if (!draft) return;
    if (draft.endTime <= draft.startTime) {
      notify('error', 'Invalid hours', 'End time must be after start time.');
      return;
    }
    setSaving(true);
    try {
      await api.admin.updateSchedule(draft);
      notify('success', 'Availability saved', 'Patients will see the new schedule immediately.');
      schedule.reload();
    } catch (err) {
      notify('error', 'Could not save', getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  if (doctors.isLoading && !doctors.data) return <Spinner />;
  if (!doctors.data?.length) return <EmptyState title="No doctors yet" description="Add a doctor first to configure availability." />;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Card className="p-4">
        <Field label="Doctor" htmlFor="sched-doctor">
          <Select id="sched-doctor" value={doctorId} onChange={(e) => { setDraft(null); setDoctorId(e.target.value); }}>
            {doctors.data.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} — {d.specialization}
              </option>
            ))}
          </Select>
        </Field>
      </Card>

      {!draft || schedule.isLoading ? (
        <Spinner label="Loading schedule…" />
      ) : (
        <>
          <Card>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Working days</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {WEEKDAYS.map((day) => {
                const on = draft.workingDays.includes(day);
                return (
                  <button
                    key={day}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleDay(day)}
                    className={cn(
                      'h-10 w-14 rounded-lg border text-sm font-medium transition',
                      on ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-300',
                    )}
                  >
                    {WEEKDAY_LABELS[day]}
                  </button>
                );
              })}
            </div>
          </Card>

          <Card className="grid gap-4 sm:grid-cols-2">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white sm:col-span-2">Consultation hours</h2>
            <Field label="Start" htmlFor="s-start">
              <Input id="s-start" type="time" value={draft.startTime} onChange={(e) => patch({ startTime: e.target.value })} />
            </Field>
            <Field label="End" htmlFor="s-end">
              <Input id="s-end" type="time" value={draft.endTime} onChange={(e) => patch({ endTime: e.target.value })} />
            </Field>
            <Field label="Break start (optional)" htmlFor="s-bstart">
              <Input id="s-bstart" type="time" value={draft.breakStart ?? ''} onChange={(e) => patch({ breakStart: e.target.value || undefined })} />
            </Field>
            <Field label="Break end (optional)" htmlFor="s-bend">
              <Input id="s-bend" type="time" value={draft.breakEnd ?? ''} onChange={(e) => patch({ breakEnd: e.target.value || undefined })} />
            </Field>
            <Field label="Slot length" htmlFor="s-slot">
              <Select id="s-slot" value={draft.slotMinutes} onChange={(e) => patch({ slotMinutes: Number(e.target.value) })}>
                {SLOT_OPTIONS.map((m) => (
                  <option key={m} value={m}>
                    {m} minutes
                  </option>
                ))}
              </Select>
            </Field>
          </Card>

          <Card>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Blocked dates</h2>
            <p className="text-xs text-slate-500">Leave, conferences or holidays — no slots are offered on these days.</p>
            <div className="mt-3 flex gap-2">
              <Input type="date" min={todayISO()} value={blockDate} onChange={(e) => setBlockDate(e.target.value)} aria-label="Date to block" className="max-w-xs" />
              <Button variant="secondary" onClick={addBlocked} disabled={!blockDate}>
                Block date
              </Button>
            </div>
            {draft.blockedDates.length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-2">
                {draft.blockedDates.map((d) => (
                  <li key={d} className="inline-flex items-center gap-1 rounded-full bg-rose-50 py-1 pl-3 pr-1 text-xs text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
                    {formatLongDate(d)}
                    <button
                      type="button"
                      aria-label={`Unblock ${d}`}
                      onClick={() => patch({ blockedDates: draft.blockedDates.filter((x) => x !== d) })}
                      className="rounded-full p-0.5 hover:bg-rose-100 dark:hover:bg-rose-500/20"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => schedule.data && setDraft(schedule.data)}>
              Reset
            </Button>
            <Button onClick={save} isLoading={saving}>
              Save availability
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
