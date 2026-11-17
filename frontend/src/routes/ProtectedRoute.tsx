import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/ui';
import type { Role } from '@/types';

interface ProtectedRouteProps {
  role?: Role;
}

export function homePathFor(role: Role): string {
  return role === 'admin' ? '/admin' : '/';
}

/** Gate a route subtree on authentication and, optionally, a specific role. */
export function ProtectedRoute({ role }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) return <Spinner label="Restoring your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (role && user.role !== role) return <Navigate to={homePathFor(user.role)} replace />;
  return <Outlet />;
}

/** For /login and /register: bounce signed-in users to their home page. */
export function GuestOnlyRoute() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <Spinner />;
  if (user) return <Navigate to={homePathFor(user.role)} replace />;
  return <Outlet />;
}
