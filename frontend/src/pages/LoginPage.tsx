import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { isMockApi } from '@/api';
import { DEMO_ACCOUNTS } from '@/data/seed';
import { getErrorMessage } from '@/lib/errors';
import { homePathFor } from '@/routes/ProtectedRoute';
import { Button, Field, Input } from '@/components/ui';
import { AuthLayout } from './AuthLayout';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from;

  const onSubmit = async (e: FormEvent): Promise<void> => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setError('Enter your email and password.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const user = await login({ email, password });
      navigate(from && user.role === 'patient' ? from : homePathFor(user.role), { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to book and manage your appointments.">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <Field label="Email" htmlFor="email">
          <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password" htmlFor="password">
          <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error && (
          <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" isLoading={submitting}>
          Sign in
        </Button>
      </form>

      {isMockApi && (
        <div className="mt-6 rounded-xl bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          <p className="font-medium">Demo mode (mock API) — fill a demo account:</p>
          <div className="mt-2 flex gap-2">
            {DEMO_ACCOUNTS.map((acc) => (
              <Button
                key={acc.id}
                size="sm"
                variant="secondary"
                onClick={() => {
                  setEmail(acc.email);
                  setPassword(acc.password);
                }}
              >
                {acc.role === 'admin' ? 'Admin' : 'Patient'}
              </Button>
            ))}
          </div>
        </div>
      )}

      <p className="mt-6 text-center text-sm text-slate-500">
        New here?{' '}
        <Link to="/register" className="font-medium text-brand-600 hover:underline">
          Create a patient account
        </Link>
      </p>
    </AuthLayout>
  );
}
