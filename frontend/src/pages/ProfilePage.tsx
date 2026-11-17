import { useState, type FormEvent } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useToast } from '@/context/ToastContext';
import { getErrorMessage } from '@/lib/errors';
import { todayISO } from '@/lib/date';
import { Avatar, Button, Card, Field, Input } from '@/components/ui';

export function ProfilePage() {
  const { user, updateProfile } = useAuth();
  const { notify } = useToast();
  const [fullName, setFullName] = useState(user?.fullName ?? '');
  const [phone, setPhone] = useState(user?.phone ?? '');
  const [dateOfBirth, setDateOfBirth] = useState(user?.dateOfBirth ?? '');
  const [saving, setSaving] = useState(false);

  if (!user) return null;

  const onSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    if (phone && !/^[+\d][\d\s-]{6,}$/.test(phone)) {
      notify('error', 'Invalid phone number');
      return;
    }
    setSaving(true);
    try {
      await updateProfile({ fullName, phone: phone || undefined, dateOfBirth: dateOfBirth || undefined });
      notify('success', 'Profile updated');
    } catch (err) {
      notify('error', 'Could not save profile', getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <div className="flex items-center gap-4">
          <Avatar name={user.fullName} size={64} />
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-white">{user.fullName}</p>
            <p className="text-sm text-slate-500">{user.email}</p>
            <p className="text-xs text-slate-400">Member since {new Date(user.createdAt).toLocaleDateString()}</p>
          </div>
        </div>
        <form onSubmit={onSubmit} className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Full name" htmlFor="pf-name">
              <Input id="pf-name" value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} />
            </Field>
          </div>
          <Field label="Phone" htmlFor="pf-phone">
            <Input id="pf-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+880 1XXX-XXXXXX" />
          </Field>
          <Field label="Date of birth" htmlFor="pf-dob">
            <Input id="pf-dob" type="date" max={todayISO()} value={dateOfBirth} onChange={(e) => setDateOfBirth(e.target.value)} />
          </Field>
          <div className="sm:col-span-2 flex justify-end">
            <Button type="submit" isLoading={saving}>
              Save changes
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
