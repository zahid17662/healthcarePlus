import { Sparkles } from 'lucide-react';
import type { Recommendation } from '@/types';
import { formatLongDate, formatTime12 } from '@/lib/date';
import { Avatar, Button, StarRating } from '@/components/ui';

interface RecommendationPanelProps {
  specialization: string;
  items: Recommendation[];
  isLoading: boolean;
  onPick: (rec: Recommendation) => void;
}

/** Bonus feature: alternative doctors in the same specialty, ranked by earliest open slot then rating. */
export function RecommendationPanel({ specialization, items, isLoading, onPick }: RecommendationPanelProps) {
  return (
    <section
      aria-live="polite"
      className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-500/30 dark:bg-amber-500/10"
    >
      <div className="flex items-center gap-2 text-amber-800 dark:text-amber-200">
        <Sparkles className="h-4 w-4" aria-hidden />
        <p className="text-sm font-semibold">No open slots — other {specialization} doctors available soon</p>
      </div>
      {isLoading ? (
        <p className="mt-3 text-sm text-amber-700">Finding alternatives…</p>
      ) : items.length === 0 ? (
        <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">
          No other {specialization} doctors have openings in the next two weeks. Try another date.
        </p>
      ) : (
        <ul className="mt-3 grid gap-2 sm:grid-cols-2 2xl:grid-cols-3">
          {items.map((rec) => (
            <li key={rec.doctor.id} className="flex items-center gap-3 rounded-xl bg-white p-3 dark:bg-slate-900">
              <Avatar src={rec.doctor.imageUrl} name={rec.doctor.name} size={40} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-slate-900 dark:text-white">{rec.doctor.name}</p>
                <p className="text-xs text-slate-500">
                  {formatLongDate(rec.date)} · {formatTime12(rec.startTime)}
                </p>
                <StarRating value={rec.doctor.averageRating} />
              </div>
              <Button size="sm" onClick={() => onPick(rec)}>
                Select
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
