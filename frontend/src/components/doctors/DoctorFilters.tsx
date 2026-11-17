import { Search } from 'lucide-react';
import { Input, Select } from '@/components/ui';

interface DoctorFiltersProps {
  query: string;
  onQueryChange: (q: string) => void;
  specialization: string;
  onSpecializationChange: (s: string) => void;
  specializations: string[];
}

export function DoctorFilters({ query, onQueryChange, specialization, onSpecializationChange, specializations }: DoctorFiltersProps) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
        <Input
          type="search"
          aria-label="Search doctors by name or specialty"
          placeholder="Search doctor or specialty…"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          className="pl-9"
        />
      </div>
      <Select
        aria-label="Filter by specialization"
        value={specialization}
        onChange={(e) => onSpecializationChange(e.target.value)}
        className="sm:w-52"
      >
        <option value="">All specializations</option>
        {specializations.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </Select>
    </div>
  );
}
