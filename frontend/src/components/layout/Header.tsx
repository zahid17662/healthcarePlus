import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, LogOut, Moon, Sun } from 'lucide-react';
import { api } from '@/api';
import { useAuth } from '@/context/AuthContext';
import { useTheme } from '@/context/ThemeContext';
import { onNotificationsChanged } from '@/lib/events';
import { Avatar } from '@/components/ui';
import type { Notification } from '@/types';

const POLL_INTERVAL_MS = 30_000;

function NotificationBell() {
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const unread = items.filter((n) => !n.read).length;

  const load = useCallback(() => {
    api.notifications.list().then(setItems).catch(() => undefined);
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    const off = onNotificationsChanged(load);
    return () => {
      clearInterval(id);
      off();
    };
  }, [load]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent): void => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [open]);

  const toggle = (): void => {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      api.notifications
        .markAllRead()
        .then(() => setItems((list) => list.map((n) => ({ ...n, read: true }))))
        .catch(() => undefined);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={toggle}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`}
        aria-expanded={open}
        className="relative rounded-full p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-800 dark:bg-slate-900">
          <p className="px-3 py-2 text-sm font-semibold text-slate-900 dark:text-white">Notifications</p>
          {items.length === 0 ? (
            <p className="px-3 py-6 text-center text-sm text-slate-500">You're all caught up.</p>
          ) : (
            <ul className="max-h-80 overflow-y-auto">
              {items.map((n) => (
                <li key={n.id} className="rounded-xl px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800">
                  <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{n.title}</p>
                  <p className="text-xs text-slate-500">{n.message}</p>
                  <p className="mt-0.5 text-[11px] text-slate-400">{new Date(n.createdAt).toLocaleString()}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function Header({ title }: { title: string }) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  if (!user) return null;

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90 md:px-8">
      <h1 className="truncate text-lg font-semibold text-slate-900 dark:text-white md:text-xl">{title}</h1>
      <div className="flex items-center gap-1 sm:gap-2">
        <NotificationBell />
        <button
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          className="rounded-full p-2 text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
        <div className="ml-1 flex items-center gap-3 border-l border-slate-200 pl-3 dark:border-slate-800">
          <Avatar name={user.fullName} size={36} />
          <div className="hidden leading-tight sm:block">
            <p className="text-sm font-semibold text-slate-900 dark:text-white">{user.fullName}</p>
            <p className="text-xs capitalize text-slate-500">{user.role}</p>
          </div>
          <button onClick={logout} aria-label="Sign out" className="rounded-full p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 md:hidden">
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
