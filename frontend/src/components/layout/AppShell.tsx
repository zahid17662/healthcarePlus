import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

const TITLES: Record<string, string> = {
  '/': 'Book an Appointment',
  '/appointments': 'My Appointments',
  '/profile': 'My Profile',
  '/admin': 'Admin Dashboard',
  '/admin/appointments': 'Appointment Management',
  '/admin/doctors': 'Doctor Directory',
  '/admin/schedules': 'Doctor Availability',
};

export function AppShell() {
  const { pathname } = useLocation();
  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header title={TITLES[pathname] ?? 'MediBook'} />
        <main className="flex-1 px-4 pb-24 pt-6 md:px-8 md:pb-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
