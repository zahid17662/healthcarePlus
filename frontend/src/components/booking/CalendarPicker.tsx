import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { WEEKDAY_LABELS, addDays, monthGrid, parseISODate, todayISO } from '@/lib/date';
import { cn } from '@/lib/cn';

/** Patients can book up to this many days ahead. */
export const BOOKING_WINDOW_DAYS = 60;

interface CalendarPickerProps {
  value: string;
  onChange: (date: string) => void;
}

export function CalendarPicker({ value, onChange }: CalendarPickerProps) {
  const today = todayISO();
  const maxDate = addDays(today, BOOKING_WINDOW_DAYS);
  const initial = parseISODate(value);
  const [view, setView] = useState({ year: initial.getFullYear(), month: initial.getMonth() });

  // Follow external date changes (e.g. picking a recommendation in another month).
  useEffect(() => {
    const d = parseISODate(value);
    setView({ year: d.getFullYear(), month: d.getMonth() });
  }, [value]);

  const shift = (delta: number): void =>
    setView(({ year, month }) => {
      const d = new Date(year, month + delta, 1);
      return { year: d.getFullYear(), month: d.getMonth() };
    });

  const viewKey = `${view.year}-${String(view.month + 1).padStart(2, '0')}`;
  const monthLabel = new Date(view.year, view.month, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  const canGoBack = viewKey > today.slice(0, 7);
  const canGoForward = viewKey < maxDate.slice(0, 7);

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-semibold text-slate-900 dark:text-white">{monthLabel}</p>
        <div className="flex gap-1">
          <button
            type="button"
            aria-label="Previous month"
            disabled={!canGoBack}
            onClick={() => shift(-1)}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="Next month"
            disabled={!canGoForward}
            onClick={() => shift(1)}
            className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 disabled:opacity-30 dark:hover:bg-slate-800"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center">
        {WEEKDAY_LABELS.map((d) => (
          <span key={d} className="py-1 text-[11px] font-medium uppercase text-slate-400" aria-hidden>
            {d.slice(0, 2)}
          </span>
        ))}
        {monthGrid(view.year, view.month).map((date, i) => {
          if (!date) return <span key={`pad-${i}`} />;
          const disabled = date < today || date > maxDate;
          const selected = date === value;
          return (
            <button
              key={date}
              type="button"
              disabled={disabled}
              aria-pressed={selected}
              aria-label={parseISODate(date).toDateString()}
              onClick={() => onChange(date)}
              className={cn(
                'aspect-square rounded-lg text-sm transition',
                selected
                  ? 'bg-brand-600 font-semibold text-white'
                  : 'text-slate-700 hover:bg-brand-50 dark:text-slate-200 dark:hover:bg-slate-800',
                date === today && !selected && 'font-semibold text-brand-600 ring-1 ring-brand-200 dark:ring-brand-800',
                disabled && 'cursor-not-allowed text-slate-300 hover:bg-transparent dark:text-slate-700 dark:hover:bg-transparent',
              )}
            >
              {Number(date.slice(8))}
            </button>
          );
        })}
      </div>
    </div>
  );
}
