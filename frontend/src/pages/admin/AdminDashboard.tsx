import { useState, type ReactNode } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Activity, CalendarCheck2, Percent, Stethoscope } from 'lucide-react';
import { api } from '@/api';
import { formatLongDate, todayISO } from '@/lib/date';
import { useAsync } from '@/lib/hooks';
import { Button, Card, EmptyState, Input, Spinner } from '@/components/ui';

const CHART_COLORS = { bookings: '#337bff', cancelled: '#f43f5e', demand: '#10b981', axis: '#94a3b8', grid: '#94a3b833' };

export function AdminDashboard() {
  const [date, setDate] = useState(todayISO);
  const stats = useAsync(() => api.admin.stats(date), [date]);
  const s = stats.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">Daily overview</p>
          <p className="text-lg font-semibold text-slate-900 dark:text-white">{formatLongDate(date)}</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          Date
          <Input type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} className="w-44" />
        </label>
      </div>

      {stats.isLoading && !s ? (
        <Spinner label="Crunching numbers…" />
      ) : stats.error || !s ? (
        <EmptyState title="Couldn't load statistics" description={stats.error ?? undefined} action={<Button onClick={stats.reload}>Retry</Button>} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi icon={<CalendarCheck2 className="h-5 w-5" />} label="Bookings" value={s.totalBookings} sub={`${s.confirmed} confirmed · ${s.pending} pending`} />
            <Kpi icon={<Activity className="h-5 w-5" />} label="Completed" value={s.completed} sub="consultations done" />
            <Kpi icon={<Percent className="h-5 w-5" />} label="Cancellation rate" value={`${Math.round(s.cancellationRate * 100)}%`} sub={`${s.cancelled} cancelled`} />
            <Kpi icon={<Stethoscope className="h-5 w-5" />} label="Active doctors" value={s.activeDoctors} sub="on duty this day" />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Booking volume — last 7 days</h2>
              <div className="mt-4 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={s.last7Days.map((d) => ({ ...d, label: d.date.slice(5) }))}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
                    <XAxis dataKey="label" tick={{ fill: CHART_COLORS.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fill: CHART_COLORS.axis, fontSize: 12 }} axisLine={false} tickLine={false} width={28} />
                    <Tooltip cursor={{ fill: '#94a3b81a' }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="bookings" name="Bookings" fill={CHART_COLORS.bookings} radius={[4, 4, 0, 0]} />
                    <Bar dataKey="cancelled" name="Cancelled" fill={CHART_COLORS.cancelled} radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Specialty demand</h2>
              {s.bySpecialty.length === 0 ? (
                <p className="mt-10 text-center text-sm text-slate-500">No active bookings on this day.</p>
              ) : (
                <div className="mt-4 h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={s.bySpecialty} layout="vertical" margin={{ left: 16 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
                      <XAxis type="number" allowDecimals={false} tick={{ fill: CHART_COLORS.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
                      <YAxis type="category" dataKey="specialization" width={110} tick={{ fill: CHART_COLORS.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
                      <Tooltip cursor={{ fill: '#94a3b81a' }} />
                      <Bar dataKey="count" name="Bookings" fill={CHART_COLORS.demand} radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

interface KpiProps {
  icon: ReactNode;
  label: string;
  value: number | string;
  sub: string;
}

function Kpi({ icon, label, value, sub }: KpiProps) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-brand-600">
        {icon}
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <p className="mt-2 text-2xl font-bold tabular-nums text-slate-900 dark:text-white">{value}</p>
      <p className="text-xs text-slate-500">{sub}</p>
    </Card>
  );
}
