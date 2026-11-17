import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2 } from 'lucide-react';
import { api } from '@/api';
import type { Appointment, Doctor, Recommendation } from '@/types';
import { useToast } from '@/context/ToastContext';
import { formatLongDate, formatTime12, todayISO } from '@/lib/date';
import { getErrorMessage, isSlotConflict } from '@/lib/errors';
import { emitNotificationsChanged } from '@/lib/events';
import { useAsync, useDebounce } from '@/lib/hooks';
import { Button, EmptyState, Modal, Spinner } from '@/components/ui';
import { BookingPanel } from '@/components/booking/BookingPanel';
import { DoctorCard } from '@/components/doctors/DoctorCard';
import { DoctorDetail } from '@/components/doctors/DoctorDetail';
import { DoctorFilters } from '@/components/doctors/DoctorFilters';
import { RecommendationPanel } from '@/components/doctors/RecommendationPanel';

const SEARCH_DEBOUNCE_MS = 300;
/** Re-poll the slot grid so other patients' bookings show up without a reload. */
const AVAILABILITY_REFRESH_MS = 20_000;
const MIN_CONCERNS_LENGTH = 5;
const XL_BREAKPOINT_PX = 1280;

export function BookingWorkspace() {
  const { notify } = useToast();
  const navigate = useNavigate();

  // Directory filters
  const [query, setQuery] = useState('');
  const [specialization, setSpecialization] = useState('');
  const debouncedQuery = useDebounce(query, SEARCH_DEBOUNCE_MS);
  const doctors = useAsync(() => api.doctors.list({ q: debouncedQuery, specialization }), [debouncedQuery, specialization]);
  const specializations = useAsync(() => api.doctors.specializations(), []);

  // Booking selection
  const [doctor, setDoctor] = useState<Doctor | null>(null);
  const [date, setDate] = useState(todayISO);
  const [slot, setSlot] = useState<string | null>(null);
  const [concerns, setConcerns] = useState('');
  const [concernsError, setConcernsError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [confirmed, setConfirmed] = useState<Appointment | null>(null);

  const availability = useAsync(() => api.doctors.availability(doctor?.id ?? '', date), [doctor?.id, date], Boolean(doctor));
  const current = availability.data?.doctorId === doctor?.id && availability.data?.date === date ? availability.data : null;
  const noOpenSlots = Boolean(current && !current.slots.some((s) => s.status === 'available'));
  const recommendations = useAsync(
    () => api.doctors.recommendations(doctor?.id ?? '', date),
    [doctor?.id, date],
    Boolean(doctor) && noOpenSlots,
  );

  // Default to the first doctor once the directory loads.
  useEffect(() => {
    if (!doctor && doctors.data?.length) setDoctor(doctors.data[0]);
  }, [doctor, doctors.data]);

  // Keep the grid fresh while the patient is deciding.
  useEffect(() => {
    if (!doctor) return;
    const id = setInterval(availability.reload, AVAILABILITY_REFRESH_MS);
    return () => clearInterval(id);
  }, [doctor, availability.reload]);

  // Drop the selection if that slot is no longer open (someone else booked it).
  useEffect(() => {
    if (!current || !slot) return;
    const stillOpen = current.slots.some((s) => s.startTime === slot && s.status === 'available');
    if (!stillOpen) {
      setSlot(null);
      notify('info', 'Slot no longer available', 'That time was just taken — please choose another.');
    }
  }, [current, slot, notify]);

  const selectDoctor = useCallback((d: Doctor, scrollToBooking = false) => {
    setDoctor(d);
    setSlot(null);
    if (scrollToBooking && window.innerWidth < XL_BREAKPOINT_PX) {
      document.getElementById('booking-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  const pickRecommendation = (rec: Recommendation): void => {
    setDoctor(rec.doctor);
    setDate(rec.date);
    setSlot(rec.startTime);
  };

  const submit = async (): Promise<void> => {
    if (!doctor || !slot) return;
    if (concerns.trim().length < MIN_CONCERNS_LENGTH) {
      setConcernsError('Briefly describe your symptoms so the doctor can prepare.');
      return;
    }
    setConcernsError(null);
    setSubmitting(true);
    try {
      const appt = await api.appointments.book({ doctorId: doctor.id, date, startTime: slot, concerns });
      setConfirmed(appt);
      setSlot(null);
      setConcerns('');
      emitNotificationsChanged();
    } catch (err) {
      if (isSlotConflict(err)) {
        setSlot(null);
        notify('error', 'Slot already taken', getErrorMessage(err));
      } else {
        notify('error', 'Booking failed', getErrorMessage(err));
      }
    } finally {
      setSubmitting(false);
      availability.reload();
    }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[290px_minmax(0,1fr)_320px]">
      {/* Left pane: calendar, slots, symptoms */}
      <div className="order-2 xl:order-1">
        <BookingPanel
          doctor={doctor}
          date={date}
          onDateChange={(d) => {
            setDate(d);
            setSlot(null);
          }}
          availability={current}
          availabilityLoading={availability.isLoading}
          availabilityError={availability.error}
          selectedSlot={slot}
          onSlotSelect={setSlot}
          concerns={concerns}
          onConcernsChange={(v) => {
            setConcerns(v);
            if (concernsError) setConcernsError(null);
          }}
          concernsError={concernsError}
          isSubmitting={submitting}
          onSubmit={submit}
        />
      </div>

      {/* Center pane: directory */}
      <section className="order-1 min-w-0 space-y-4 xl:order-2" aria-label="Doctor directory">
        <DoctorFilters
          query={query}
          onQueryChange={setQuery}
          specialization={specialization}
          onSpecializationChange={setSpecialization}
          specializations={specializations.data ?? []}
        />
        {doctor && noOpenSlots && (
          <RecommendationPanel
            specialization={doctor.specialization}
            items={recommendations.data ?? []}
            isLoading={recommendations.isLoading}
            onPick={pickRecommendation}
          />
        )}
        {doctors.isLoading && !doctors.data ? (
          <Spinner label="Loading doctors…" />
        ) : doctors.error ? (
          <EmptyState title="Couldn't load doctors" description={doctors.error} action={<Button onClick={doctors.reload}>Retry</Button>} />
        ) : !doctors.data?.length ? (
          <EmptyState title="No doctors match your search" description="Try a different name or clear the specialization filter." />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            {doctors.data.map((d) => (
              <DoctorCard
                key={d.id}
                doctor={d}
                isSelected={d.id === doctor?.id}
                onBook={(x) => selectDoctor(x, true)}
                onDetail={(x) => {
                  selectDoctor(x);
                  setDetailOpen(true);
                }}
                onChat={(x) => notify('info', 'Messaging coming soon', `Secure chat with ${x.name} will be available shortly.`)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Right pane: detail drawer (static on xl, overlay below) */}
      <aside className="order-3 hidden overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 xl:sticky xl:top-20 xl:block xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto">
        <DoctorDetail doctor={doctor} onBook={(d) => selectDoctor(d, true)} />
      </aside>
      {detailOpen && doctor && (
        <div className="fixed inset-0 z-40 flex justify-end bg-slate-900/50 xl:hidden" onClick={() => setDetailOpen(false)}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`${doctor.name} profile`}
            className="h-full w-full max-w-md overflow-y-auto bg-white dark:bg-slate-900"
            onClick={(e) => e.stopPropagation()}
          >
            <DoctorDetail
              doctor={doctor}
              onClose={() => setDetailOpen(false)}
              onBook={(d) => {
                setDetailOpen(false);
                selectDoctor(d, true);
              }}
            />
          </div>
        </div>
      )}

      <Modal
        open={confirmed !== null}
        title="Appointment confirmed"
        onClose={() => setConfirmed(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => navigate('/appointments')}>
              View my appointments
            </Button>
            <Button onClick={() => setConfirmed(null)}>Done</Button>
          </>
        }
      >
        {confirmed && (
          <div className="flex gap-3">
            <CheckCircle2 className="h-10 w-10 shrink-0 text-emerald-500" aria-hidden />
            <div className="text-sm text-slate-600 dark:text-slate-300">
              <p>
                Your slot with <strong className="text-slate-900 dark:text-white">{confirmed.doctorName}</strong> is locked in.
              </p>
              <p className="mt-1">
                {formatLongDate(confirmed.date)} · {formatTime12(confirmed.startTime)} – {formatTime12(confirmed.endTime)}
              </p>
              <p className="mt-1 text-xs text-slate-500">Reference #{confirmed.id.slice(-8).toUpperCase()} · A confirmation was added to your notifications.</p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
