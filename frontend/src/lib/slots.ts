import type { Appointment, DayAvailability, DoctorSchedule, TimeSlot, Weekday } from '@/types';
import { minutesToTime, parseISODate, timeToMinutes, todayISO } from './date';

interface BuildAvailabilityArgs {
  schedule: DoctorSchedule;
  date: string;
  appointments: readonly Appointment[];
  now?: Date;
}

/** Slot key used for the (doctor, date, start) uniqueness rule. */
export function slotKey(doctorId: string, date: string, startTime: string): string {
  return `${doctorId}|${date}|${startTime}`;
}

export function isWorkingDay(schedule: DoctorSchedule, date: string): boolean {
  const weekday = parseISODate(date).getDay() as Weekday;
  return schedule.workingDays.includes(weekday) && !schedule.blockedDates.includes(date);
}

function inBreak(schedule: DoctorSchedule, start: number, end: number): boolean {
  if (!schedule.breakStart || !schedule.breakEnd) return false;
  const bs = timeToMinutes(schedule.breakStart);
  const be = timeToMinutes(schedule.breakEnd);
  return start < be && end > bs;
}

/**
 * Builds the slot grid for one doctor/day. Shared by the mock API; a real backend
 * should compute the same thing server-side.
 */
export function buildAvailability({ schedule, date, appointments, now = new Date() }: BuildAvailabilityArgs): DayAvailability {
  const working = isWorkingDay(schedule, date);
  if (!working) return { doctorId: schedule.doctorId, date, isWorkingDay: false, slots: [] };

  const taken = new Set(
    appointments
      .filter((a) => a.doctorId === schedule.doctorId && a.date === date && a.status !== 'cancelled')
      .map((a) => a.startTime),
  );
  const isToday = date === todayISO();
  const nowMinutes = now.getHours() * 60 + now.getMinutes();
  const isPastDay = date < todayISO();

  const startMin = timeToMinutes(schedule.startTime);
  const endMin = timeToMinutes(schedule.endTime);
  const count = Math.max(0, Math.floor((endMin - startMin) / schedule.slotMinutes));

  const slots: TimeSlot[] = Array.from({ length: count }, (_, i) => {
    const s = startMin + i * schedule.slotMinutes;
    const e = s + schedule.slotMinutes;
    const startTime = minutesToTime(s);
    const status: TimeSlot['status'] = inBreak(schedule, s, e)
      ? 'blocked'
      : isPastDay || (isToday && s <= nowMinutes)
        ? 'past'
        : taken.has(startTime)
          ? 'booked'
          : 'available';
    return { startTime, endTime: minutesToTime(e), status };
  });

  return { doctorId: schedule.doctorId, date, isWorkingDay: true, slots };
}
