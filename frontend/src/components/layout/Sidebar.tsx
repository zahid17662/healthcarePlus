import { NavLink } from 'react-router-dom';
import { CalendarCheck, CalendarDays, ClipboardList, HeartPulse, LayoutDashboard, LogOut, Stethoscope, UserRound, type LucideIcon } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/cn';
import type { Role } from '@/types';

interface NavItem {
  to: string;
  label: string;
  short: string;
  icon: LucideIcon;
}

const NAV_ITEMS: Record<Role, NavItem[]> = {
  patient: [
    { to: '/', label: 'Book Appointment', short: 'Book', icon: CalendarDays },
    { to: '/appointments', label: 'My Appointments', short: 'Visits', icon: CalendarCheck },
    { to: '/profile', label: 'Profile', short: 'Profile', icon: UserRound },
  ],
  admin: [
    { to: '/admin', label: 'Dashboard', short: 'Stats', icon: LayoutDashboard },
    { to: '/admin/appointments', label: 'Appointments', short: 'Bookings', icon: ClipboardList },
    { to: '/admin/doctors', label: 'Doctors', short: 'Doctors', icon: Stethoscope },
    { to: '/admin/schedules', label: 'Availability', short: 'Hours', icon: CalendarDays },
    { to: '/profile', label: 'Profile', short: 'Profile', icon: UserRound },
  ],
};

const isRootLink = (to: string): boolean => to === '/' || to === '/admin';

const linkClass = ({ isActive }: { isActive: boolean }): string =>
  cn(
    'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition',
    isActive
      ? 'bg-brand-600 text-white shadow-sm'
      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
  );

export function Sidebar() {
  const { user, logout } = useAuth();
  if (!user) return null;
  const items = NAV_ITEMS[user.role];

  return (
    <>
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white px-4 py-6 dark:border-slate-800 dark:bg-slate-950 md:flex">
        <div className="mb-8 flex items-center gap-2 px-2">
          <HeartPulse className="h-7 w-7 text-brand-600" aria-hidden />
          <span className="text-lg font-bold text-slate-900 dark:text-white">MediBook</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1" aria-label="Main">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={isRootLink(to)} className={linkClass}>
              <Icon className="h-5 w-5" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          type="button"
          onClick={logout}
          className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-600 hover:bg-rose-50 hover:text-rose-600 dark:text-slate-300 dark:hover:bg-rose-500/10"
        >
          <LogOut className="h-5 w-5" aria-hidden />
          Sign out
        </button>
      </aside>

      <nav
        aria-label="Main mobile"
        className="fixed inset-x-0 bottom-0 z-30 flex justify-around border-t border-slate-200 bg-white/95 py-2 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95 md:hidden"
      >
        {items.map(({ to, short, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={isRootLink(to)}
            className={({ isActive }) =>
              cn('flex flex-col items-center gap-0.5 px-2 text-[11px] font-medium', isActive ? 'text-brand-600' : 'text-slate-500')
            }
          >
            <Icon className="h-5 w-5" aria-hidden />
            {short}
          </NavLink>
        ))}
      </nav>
    </>
  );
}
