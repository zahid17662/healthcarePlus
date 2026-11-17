import type { SlotStatus, TimeSlot } from '@/types';
import { formatTime12 } from '@/lib/date';
import { cn } from '@/lib/cn';

interface TimeSlotGridProps {
  slots: TimeSlot[];
  selected: string | null;
  onSelect: (startTime: string) => void;
}

const STATUS_LABEL: Record<SlotStatus, string> = {
  available: 'available',
  booked: 'already booked',
  blocked: 'unavailable (break)',
  past: 'time has passed',
};

export function TimeSlotGrid({ slots, selected, onSelect }: TimeSlotGridProps) {
  return (
    <div>
      <div className="grid grid-cols-3 gap-2" role="listbox" aria-label="Available time slots">
        {slots.map((slot) => {
          const isSelected = slot.startTime === selected;
          const isOpen = slot.status === 'available';
          return (
            <button
              key={slot.startTime}
              type="button"
              role="option"
              aria-selected={isSelected}
              disabled={!isOpen}
              title={STATUS_LABEL[slot.status]}
              aria-label={`${formatTime12(slot.startTime)}, ${STATUS_LABEL[slot.status]}`}
              onClick={() => onSelect(slot.startTime)}
              className={cn(
                'rounded-lg border px-1 py-2 text-xs font-medium transition',
                isSelected && 'border-brand-600 bg-brand-600 text-white shadow-sm',
                !isSelected && isOpen &&
                  'border-slate-200 bg-white text-slate-700 hover:border-brand-400 hover:text-brand-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200',
                slot.status === 'booked' &&
                  'cursor-not-allowed border-rose-100 bg-rose-50 text-rose-300 line-through dark:border-rose-500/20 dark:bg-rose-500/10 dark:text-rose-400/60',
                (slot.status === 'past' || slot.status === 'blocked') &&
                  'cursor-not-allowed border-transparent bg-slate-100 text-slate-300 dark:bg-slate-800 dark:text-slate-600',
              )}
            >
              {formatTime12(slot.startTime)}
            </button>
          );
        })}
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-slate-500">
        <Legend className="border border-slate-300 bg-white dark:bg-slate-900" label="Open" />
        <Legend className="bg-brand-600" label="Selected" />
        <Legend className="bg-rose-200 dark:bg-rose-500/40" label="Booked" />
        <Legend className="bg-slate-200 dark:bg-slate-700" label="Unavailable" />
      </div>
    </div>
  );
}

function Legend({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className={cn('h-2.5 w-2.5 rounded-sm', className)} aria-hidden />
      {label}
    </span>
  );
}
