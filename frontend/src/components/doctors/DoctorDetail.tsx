import type { ReactNode } from 'react';
import { Award, Briefcase, Star, X } from 'lucide-react';
import { api } from '@/api';
import type { Doctor } from '@/types';
import { formatCurrency } from '@/lib/cn';
import { useAsync } from '@/lib/hooks';
import { Avatar, Button, Spinner, StarRating } from '@/components/ui';

interface DoctorDetailProps {
  doctor: Doctor | null;
  onBook: (doctor: Doctor) => void;
  /** Present when rendered as an overlay drawer (below xl). */
  onClose?: () => void;
}

export function DoctorDetail({ doctor, onBook, onClose }: DoctorDetailProps) {
  const reviews = useAsync(() => api.doctors.reviews(doctor?.id ?? ''), [doctor?.id], Boolean(doctor));

  if (!doctor) {
    return <p className="p-6 text-center text-sm text-slate-500">Select a doctor to view their profile.</p>;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="relative bg-gradient-to-br from-brand-600 to-brand-800 px-5 pb-14 pt-5 text-white">
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Close doctor details" className="absolute right-3 top-3 rounded-full p-1.5 hover:bg-white/10">
            <X className="h-5 w-5" />
          </button>
        )}
        <p className="text-xs uppercase tracking-wide text-brand-100">Doctor profile</p>
      </div>
      <div className="-mt-10 flex flex-col items-center px-5 text-center">
        <div className="rounded-full ring-4 ring-white dark:ring-slate-900">
          <Avatar src={doctor.imageUrl} name={doctor.name} size={80} />
        </div>
        <h2 className="mt-3 text-lg font-semibold text-slate-900 dark:text-white">{doctor.name}</h2>
        <p className="text-sm text-brand-600 dark:text-brand-400">{doctor.specialization}</p>
        <div className="mt-2">
          <StarRating value={doctor.averageRating} count={doctor.reviewCount} />
        </div>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-2 px-5 text-center">
        <Stat icon={<Briefcase className="h-4 w-4" />} label="Experience" value={`${doctor.experienceYears} yrs`} />
        <Stat icon={<Star className="h-4 w-4" />} label="Reviews" value={String(doctor.reviewCount)} />
        <Stat icon={<Award className="h-4 w-4" />} label="Fee/hr" value={formatCurrency(doctor.hourlyRate)} />
      </div>

      <section className="mt-5 px-5">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">About</h3>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{doctor.bio}</p>
      </section>

      <section className="mt-4 px-5">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Treats</h3>
        <ul className="mt-2 flex flex-wrap gap-1.5">
          {doctor.subSpecialties.map((s) => (
            <li key={s} className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
              {s}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-4 flex-1 px-5">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Patient reviews</h3>
        {reviews.isLoading ? (
          <Spinner label="Loading reviews…" />
        ) : reviews.error ? (
          <p className="mt-2 text-sm text-rose-600">{reviews.error}</p>
        ) : !reviews.data?.length ? (
          <p className="mt-2 text-sm text-slate-500">No reviews yet.</p>
        ) : (
          <ul className="mt-2 space-y-3">
            {reviews.data.map((r) => (
              <li key={r.id} className="rounded-xl bg-slate-50 p-3 dark:bg-slate-800/60">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-100">{r.patientName}</span>
                  <span className="flex" aria-label={`${r.rating} out of 5 stars`}>
                    {Array.from({ length: 5 }, (_, i) => (
                      <Star key={i} className={i < r.rating ? 'h-3.5 w-3.5 fill-amber-400 text-amber-400' : 'h-3.5 w-3.5 text-slate-300'} aria-hidden />
                    ))}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{r.comment}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="sticky bottom-0 mt-4 border-t border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <Button className="w-full" onClick={() => onBook(doctor)}>
          Book with {doctor.name.replace(/^Dr\.?\s*/, 'Dr. ')}
        </Button>
      </div>
    </div>
  );
}

function Stat({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 p-2 dark:bg-slate-800/60">
      <div className="flex justify-center text-brand-600">{icon}</div>
      <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-white">{value}</p>
      <p className="text-[11px] text-slate-500">{label}</p>
    </div>
  );
}
