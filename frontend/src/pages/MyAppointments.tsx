import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CalendarClock } from 'lucide-react';
import { api } from '@/api';
import type { Appointment } from '@/types';
import { useToast } from '@/context/ToastContext';
import { formatLongDate, formatTime12, todayISO } from '@/lib/date';
import { getErrorMessage } from '@/lib/errors';
import { emitNotificationsChanged } from '@/lib/events';
import { useAsync } from '@/lib/hooks';
import { cn } from '@/lib/cn';
import { Button, Card, EmptyState, Modal, Spinner, StatusBadge } from '@/components/ui';

type Tab = 'upcoming' | 'past';

function isUpcoming(a: Appointment): boolean {
  return a.date >= todayISO() && (a.status === 'pending' || a.status === 'confirmed');
}

export function MyAppointments() {
  const { notify } = useToast();
  const navigate = useNavigate();
  const appointments = useAsync(() => api.appointments.mine(), []);
  const [tab, setTab] = useState<Tab>('upcoming');
  const [toCancel, setToCancel] = useState<Appointment | null>(null);
  const [cancelling, setCancelling] = useState(false);

  const all = appointments.data ?? [];
  const upcoming = all.filter(isUpcoming).sort((a, b) => `${a.date}${a.startTime}`.localeCompare(`${b.date}${b.startTime}`));
  const past = all.filter((a) => !isUpcoming(a));
  const list = tab === 'upcoming' ? upcoming : past;

  const confirmCancel = async (): Promise<void> => {
    if (!toCancel) return;
    setCancelling(true);
    try {
      await api.appointments.cancel(toCancel.id);
      notify('success', 'Appointment cancelled', 'The slot has been released.');
      emitNotificationsChanged();
      setToCancel(null);
      appointments.reload();
    } catch (err) {
      notify('error', 'Could not cancel', getErrorMessage(err));
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div role="tablist" aria-label="Appointment filter" className="inline-flex rounded-xl bg-slate-200/60 p-1 dark:bg-slate-800">
          {(['upcoming', 'past'] as const).map((t) => (
            <button
              key={t}
              role="tab"
              type="button"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={cn(
                'rounded-lg px-4 py-1.5 text-sm font-medium capitalize transition',
                tab === t ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-950 dark:text-white' : 'text-slate-500',
              )}
            >
              {t} ({t === 'upcoming' ? upcoming.length : past.length})
            </button>
          ))}
        </div>
        <Button onClick={() => navigate('/')}>New booking</Button>
      </div>

      {appointments.isLoading && !appointments.data ? (
        <Spinner />
      ) : appointments.error ? (
        <EmptyState title="Couldn't load appointments" description={appointments.error} action={<Button onClick={appointments.reload}>Retry</Button>} />
      ) : list.length === 0 ? (
        <EmptyState
          title={tab === 'upcoming' ? 'No upcoming appointments' : 'No past appointments'}
          description={tab === 'upcoming' ? 'Find a specialist and book a time that suits you.' : undefined}
          action={tab === 'upcoming' ? <Button onClick={() => navigate('/')}>Book now</Button> : undefined}
        />
      ) : (
        <ul className="space-y-3">
          {list.map((a) => (
            <li key={a.id}>
              <Card className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-xl bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
                  <CalendarClock className="h-5 w-5" aria-hidden />
                  <span className="text-[11px] font-semibold">{a.date.slice(5).replace('-', '/')}</span>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-slate-900 dark:text-white">{a.doctorName}</p>
                    <StatusBadge status={a.status} />
                  </div>
                  <p className="text-sm text-slate-500">
                    {a.specialization} · {formatLongDate(a.date)} · {formatTime12(a.startTime)}
                  </p>
                  {a.concerns && <p className="mt-1 line-clamp-2 text-sm text-slate-600 dark:text-slate-300">“{a.concerns}”</p>}
                </div>
                {isUpcoming(a) && (
                  <Button variant="secondary" size="sm" onClick={() => setToCancel(a)} className="self-start sm:self-center">
                    Cancel
                  </Button>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={toCancel !== null}
        title="Cancel this appointment?"
        onClose={() => setToCancel(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setToCancel(null)}>
              Keep it
            </Button>
            <Button variant="danger" isLoading={cancelling} onClick={confirmCancel}>
              Cancel appointment
            </Button>
          </>
        }
      >
        {toCancel && (
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Your visit with <strong>{toCancel.doctorName}</strong> on {formatLongDate(toCancel.date)} at {formatTime12(toCancel.startTime)} will be
            cancelled and the slot released to other patients. This can't be undone.
          </p>
        )}
      </Modal>
    </div>
  );
}
