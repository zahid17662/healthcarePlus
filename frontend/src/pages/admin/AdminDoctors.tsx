import { useState, type FormEvent } from 'react';
import { Plus } from 'lucide-react';
import { api } from '@/api';
import type { Doctor, DoctorInput } from '@/types';
import { SPECIALIZATIONS } from '@/data/seed';
import { useToast } from '@/context/ToastContext';
import { formatCurrency } from '@/lib/cn';
import { getErrorMessage } from '@/lib/errors';
import { useAsync } from '@/lib/hooks';
import { Avatar, Button, Card, EmptyState, Field, Input, Modal, Select, Spinner, StarRating, Textarea } from '@/components/ui';

const EMPTY_DOCTOR: DoctorInput = {
  name: '',
  specialization: SPECIALIZATIONS[0],
  subSpecialties: [],
  experienceYears: 1,
  bio: '',
  hourlyRate: 50,
  imageUrl: '',
  isActive: true,
};

function toInput(d: Doctor): DoctorInput {
  const { id: _id, averageRating: _r, reviewCount: _c, ...rest } = d;
  return rest;
}

export function AdminDoctors() {
  const { notify } = useToast();
  const doctors = useAsync(() => api.admin.doctors(), []);
  const [editing, setEditing] = useState<{ id: string | null; form: DoctorInput } | null>(null);
  const [subInput, setSubInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = (d?: Doctor): void => {
    const form = d ? toInput(d) : EMPTY_DOCTOR;
    setEditing({ id: d?.id ?? null, form });
    setSubInput(form.subSpecialties.join(', '));
    setError(null);
  };

  const update = <K extends keyof DoctorInput>(key: K, value: DoctorInput[K]): void =>
    setEditing((e) => (e ? { ...e, form: { ...e.form, [key]: value } } : e));

  const save = async (ev: FormEvent): Promise<void> => {
    ev.preventDefault();
    if (!editing) return;
    const form: DoctorInput = {
      ...editing.form,
      subSpecialties: subInput.split(',').map((s) => s.trim()).filter(Boolean),
    };
    if (form.name.trim().length < 3) return setError('Enter the doctor’s full name.');
    if (!(form.hourlyRate > 0)) return setError('Hourly rate must be greater than zero.');
    if (form.imageUrl && !/^https?:\/\//.test(form.imageUrl)) return setError('Photo URL must start with http(s)://');
    setSaving(true);
    setError(null);
    try {
      if (editing.id) await api.admin.updateDoctor(editing.id, form);
      else await api.admin.createDoctor(form);
      notify('success', editing.id ? 'Doctor updated' : 'Doctor added', form.name);
      setEditing(null);
      doctors.reload();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (d: Doctor): Promise<void> => {
    try {
      await api.admin.updateDoctor(d.id, { ...toInput(d), isActive: !d.isActive });
      notify('success', d.isActive ? 'Doctor hidden from patients' : 'Doctor visible to patients', d.name);
      doctors.reload();
    } catch (err) {
      notify('error', 'Update failed', getErrorMessage(err));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => open()}>
          <Plus className="h-4 w-4" aria-hidden /> Add doctor
        </Button>
      </div>

      {doctors.isLoading && !doctors.data ? (
        <Spinner />
      ) : doctors.error ? (
        <EmptyState title="Couldn't load doctors" description={doctors.error} action={<Button onClick={doctors.reload}>Retry</Button>} />
      ) : !doctors.data?.length ? (
        <EmptyState title="No doctors yet" action={<Button onClick={() => open()}>Add the first doctor</Button>} />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {doctors.data.map((d) => (
            <Card key={d.id} className={d.isActive ? '' : 'opacity-60'}>
              <div className="flex items-start gap-3">
                <Avatar src={d.imageUrl} name={d.name} size={52} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-slate-900 dark:text-white">{d.name}</p>
                  <p className="text-sm text-brand-600">{d.specialization}</p>
                  <div className="mt-1 flex items-center gap-3 text-xs text-slate-500">
                    <StarRating value={d.averageRating} count={d.reviewCount} />
                    <span>{formatCurrency(d.hourlyRate)}/hr</span>
                    <span>{d.experienceYears} yrs</span>
                  </div>
                </div>
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <Button size="sm" variant="ghost" onClick={() => toggleActive(d)}>
                  {d.isActive ? 'Deactivate' : 'Activate'}
                </Button>
                <Button size="sm" variant="secondary" onClick={() => open(d)}>
                  Edit
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={editing !== null} title={editing?.id ? 'Edit doctor' : 'Add doctor'} onClose={() => setEditing(null)}>
        {editing && (
          <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="Full name" htmlFor="doc-name">
                <Input id="doc-name" value={editing.form.name} onChange={(e) => update('name', e.target.value)} placeholder="Dr. Jane Doe" />
              </Field>
            </div>
            <Field label="Specialization" htmlFor="doc-spec">
              <Select id="doc-spec" value={editing.form.specialization} onChange={(e) => update('specialization', e.target.value)}>
                {SPECIALIZATIONS.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </Select>
            </Field>
            <Field label="Hourly rate (USD)" htmlFor="doc-rate">
              <Input id="doc-rate" type="number" min={1} value={editing.form.hourlyRate} onChange={(e) => update('hourlyRate', Number(e.target.value))} />
            </Field>
            <Field label="Years of experience" htmlFor="doc-exp">
              <Input id="doc-exp" type="number" min={0} value={editing.form.experienceYears} onChange={(e) => update('experienceYears', Number(e.target.value))} />
            </Field>
            <Field label="Photo URL" htmlFor="doc-img">
              <Input id="doc-img" type="url" value={editing.form.imageUrl} onChange={(e) => update('imageUrl', e.target.value)} placeholder="https://…" />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Treatment specialties" htmlFor="doc-subs" hint="Comma-separated, e.g. Migraine, Epilepsy">
                <Input id="doc-subs" value={subInput} onChange={(e) => setSubInput(e.target.value)} />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field label="Bio" htmlFor="doc-bio">
                <Textarea id="doc-bio" rows={3} value={editing.form.bio} onChange={(e) => update('bio', e.target.value)} />
              </Field>
            </div>
            {error && (
              <p role="alert" className="text-sm text-rose-600 sm:col-span-2">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-2 sm:col-span-2">
              <Button variant="secondary" onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button type="submit" isLoading={saving}>
                Save doctor
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
