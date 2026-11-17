import type { FormEvent } from 'react';
import { CalendarX2 } from 'lucide-react';
import type { DayAvailability, Doctor } from '@/types';
import { formatLongDate, formatTime12 } from '@/lib/date';
import { formatCurrency } from '@/lib/cn';
import { Button, Card, Spinner, Textarea } from '@/components/ui';
import { CalendarPicker } from './CalendarPicker';
import { TimeSlotGrid } from './TimeSlotGrid';

export const MAX_CONCERNS_LENGTH = 1000;

interface BookingPanelProps {
  doctor: Doctor | null;
  date: string;
  onDateChange: (date: string) => void;
  availability: DayAvailability | null;
  availabilityLoading: boolean;
  availabilityError: string | null;
  selectedSlot: string | null;
  onSlotSelect: (startTime: string) => void;
  concerns: string;
  onConcernsChange: (value: string) => void;
  concernsError: string | null;
  isSubmitting: boolean;
  onSubmit: () => void;
}

export function BookingPanel(props: BookingPanelProps) {
  const { doctor, date, availability, selectedSlot, concerns, isSubmitting } = props;
  const openCount = availability?.slots.filter((s) => s.status === 'available').length ?? 0;

  const submit = (e: FormEvent): void => {
    e.preventDefault();
    props.onSubmit();
  };

  return (
    <form onSubmit={submit} className="space-y-4" id="booking-panel" aria-label="Book appointment">
      <Card className="p-4">
        <CalendarPicker value={date} onChange={props.onDateChange} />
      </Card>

      <Card className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-slate-900 dark:text-white">Available time</p>
          {availability?.isWorkingDay && <span className="text-xs text-slate-500">{openCount} open</span>}
        </div>
        {!doctor ? (
          <p className="text-sm text-slate-500">Select a doctor to see their schedule.</p>
        ) : props.availabilityLoading && !availability ? (
          <Spinner label="Checking schedule…" />
        ) : props.availabilityError ? (
          <p className="text-sm text-rose-600">{props.availabilityError}</p>
        ) : availability && !availability.isWorkingDay ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center text-sm text-slate-500">
            <CalendarX2 className="h-6 w-6" aria-hidden />
            {doctor.name} is not available on {formatLongDate(date)}.
          </div>
        ) : availability ? (
          <TimeSlotGrid slots={availability.slots} selected={selectedSlot} onSelect={props.onSlotSelect} />
        ) : null}
      </Card>

      <Card className="p-4">
        <label htmlFor="concerns" className="text-sm font-semibold text-slate-900 dark:text-white">
          Concerns &amp; symptoms
        </label>
        <Textarea
          id="concerns"
          rows={4}
          maxLength={MAX_CONCERNS_LENGTH}
          value={concerns}
          onChange={(e) => props.onConcernsChange(e.target.value)}
          placeholder="e.g. Chest discomfort for 3 days, worse when climbing stairs…"
          className="mt-2"
          aria-invalid={Boolean(props.concernsError)}
          aria-describedby="concerns-help"
        />
        <div id="concerns-help" className="mt-1 flex justify-between text-xs">
          <span className="text-rose-600">{props.concernsError}</span>
          <span className="text-slate-400">
            {concerns.length}/{MAX_CONCERNS_LENGTH}
          </span>
        </div>
      </Card>

      {doctor && selectedSlot && (
        <div className="rounded-2xl bg-brand-50 p-4 text-sm text-brand-900 dark:bg-brand-500/10 dark:text-brand-100">
          <p className="font-semibold">{doctor.name}</p>
          <p>
            {formatLongDate(date)} · {formatTime12(selectedSlot)}
          </p>
          <p className="text-xs opacity-80">Consultation fee {formatCurrency(doctor.hourlyRate)}/hr</p>
        </div>
      )}

      <Button type="submit" className="w-full" disabled={!doctor || !selectedSlot} isLoading={isSubmitting}>
        Confirm booking
      </Button>
    </form>
  );
}
