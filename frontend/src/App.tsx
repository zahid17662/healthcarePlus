import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { GuestOnlyRoute, ProtectedRoute } from '@/routes/ProtectedRoute';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { BookingWorkspace } from '@/pages/BookingWorkspace';
import { MyAppointments } from '@/pages/MyAppointments';
import { ProfilePage } from '@/pages/ProfilePage';
import { Spinner } from '@/components/ui';

// Admin screens (and the charting library) load only for admins.
const AdminDashboard = lazy(() => import('@/pages/admin/AdminDashboard').then((m) => ({ default: m.AdminDashboard })));
const AdminAppointments = lazy(() => import('@/pages/admin/AdminAppointments').then((m) => ({ default: m.AdminAppointments })));
const AdminDoctors = lazy(() => import('@/pages/admin/AdminDoctors').then((m) => ({ default: m.AdminDoctors })));
const AdminSchedules = lazy(() => import('@/pages/admin/AdminSchedules').then((m) => ({ default: m.AdminSchedules })));

export function App() {
  return (
    <Suspense fallback={<Spinner />}>
    <Routes>
      <Route element={<GuestOnlyRoute />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route path="/profile" element={<ProfilePage />} />

          <Route element={<ProtectedRoute role="patient" />}>
            <Route path="/" element={<BookingWorkspace />} />
            <Route path="/appointments" element={<MyAppointments />} />
          </Route>

          <Route path="/admin" element={<ProtectedRoute role="admin" />}>
            <Route index element={<AdminDashboard />} />
            <Route path="appointments" element={<AdminAppointments />} />
            <Route path="doctors" element={<AdminDoctors />} />
            <Route path="schedules" element={<AdminSchedules />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  );
}
