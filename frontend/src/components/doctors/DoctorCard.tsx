import { MessageCircle } from 'lucide-react';
import type { Doctor } from '@/types';
import { cn, formatCurrency } from '@/lib/cn';
import { Avatar, Button, StarRating } from '@/components/ui';

interface DoctorCardProps {
  doctor: Doctor;
  isSelected: boolean;
  onBook: (doctor: Doctor) => void;
  onDetail: (doctor: Doctor) => void;
  onChat: (doctor: Doctor) => void;
}

export function DoctorCard({ doctor, isSelected, onBook, onDetail, onChat }: DoctorCardProps) {
  return (
    <article
      className={cn(
        'flex flex-col rounded-2xl border bg-white p-4 transition dark:bg-slate-900',
        isSelected
          ? 'border-brand-500 ring-2 ring-brand-500/20'
          : 'border-slate-200 hover:border-slate-300 dark:border-slate-800 dark:hover:border-slate-700',
      )}
    >
      <div className="flex items-start gap-3">
        <Avatar src={doctor.imageUrl} name={doctor.name} size={56} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-semibold text-slate-900 dark:text-white">{doctor.name}</h3>
          <p className="text-sm text-brand-600 dark:text-brand-400">{doctor.specialization}</p>
          <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
            <StarRating value={doctor.averageRating} count={doctor.reviewCount} />
            <span>{doctor.experienceYears} yrs exp.</span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => onChat(doctor)}
          aria-label={`Message ${doctor.name}`}
          className="rounded-full p-2 text-slate-400 hover:bg-slate-100 hover:text-brand-600 dark:hover:bg-slate-800"
        >
          <MessageCircle className="h-5 w-5" />
        </button>
      </div>
      <div className="mt-4 flex items-center justify-between gap-2">
        <p className="text-sm">
          <span className="text-lg font-bold text-slate-900 dark:text-white">{formatCurrency(doctor.hourlyRate)}</span>
          <span className="text-slate-500">/hr</span>
        </p>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={() => onDetail(doctor)}>
            Detail
          </Button>
          <Button size="sm" onClick={() => onBook(doctor)}>
            Book Now
          </Button>
        </div>
      </div>
    </article>
  );
}
