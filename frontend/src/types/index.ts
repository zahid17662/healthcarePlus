// Shared domain models — mirror PRD §6 "Core Data Entities".

export type Role = 'patient' | 'admin';

export interface User {
  id: string;
  fullName: string;
  email: string;
  phone?: string;
  dateOfBirth?: string;
  role: Role;
  createdAt: string;
}

export interface Doctor {
  id: string;
  name: string;
  specialization: string;
  subSpecialties: string[];
  experienceYears: number;
  bio: string;
  hourlyRate: number;
  imageUrl: string;
  averageRating: number;
  reviewCount: number;
  isActive: boolean;
}

export type DoctorInput = Omit<Doctor, 'id' | 'averageRating' | 'reviewCount'>;

/** 0 = Sunday … 6 = Saturday */
export type Weekday = 0 | 1 | 2 | 3 | 4 | 5 | 6;

export interface DoctorSchedule {
  doctorId: string;
  workingDays: Weekday[];
  startTime: string; // "HH:mm"
  endTime: string; // "HH:mm"
  slotMinutes: number;
  breakStart?: string;
  breakEnd?: string;
  blockedDates: string[]; // "YYYY-MM-DD"
}

export type SlotStatus = 'available' | 'booked' | 'blocked' | 'past';

export interface TimeSlot {
  startTime: string;
  endTime: string;
  status: SlotStatus;
}

export interface DayAvailability {
  doctorId: string;
  date: string;
  isWorkingDay: boolean;
  slots: TimeSlot[];
}

export type AppointmentStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled';

export interface Appointment {
  id: string;
  patientId: string;
  patientName: string;
  doctorId: string;
  doctorName: string;
  specialization: string;
  date: string;
  startTime: string;
  endTime: string;
  concerns: string;
  status: AppointmentStatus;
  createdAt: string;
  updatedAt: string;
}

export interface BookingRequest {
  doctorId: string;
  date: string;
  startTime: string;
  concerns: string;
}

export interface Review {
  id: string;
  doctorId: string;
  patientName: string;
  rating: number;
  comment: string;
  createdAt: string;
}

export interface Recommendation {
  doctor: Doctor;
  date: string;
  startTime: string;
}

export interface Notification {
  id: string;
  userId: string;
  title: string;
  message: string;
  read: boolean;
  createdAt: string;
}

export interface DailyStats {
  date: string;
  totalBookings: number;
  confirmed: number;
  pending: number;
  completed: number;
  cancelled: number;
  cancellationRate: number;
  activeDoctors: number;
  bySpecialty: { specialization: string; count: number }[];
  last7Days: { date: string; bookings: number; cancelled: number }[];
}

export interface AuthSession {
  token: string;
  user: User;
}

export interface RegisterInput {
  fullName: string;
  email: string;
  password: string;
}

export interface LoginInput {
  email: string;
  password: string;
}

export type ProfileUpdate = Partial<Pick<User, 'fullName' | 'phone' | 'dateOfBirth'>>;

export interface DoctorQuery {
  q?: string;
  specialization?: string;
}

export interface AdminAppointmentQuery {
  date?: string;
  status?: AppointmentStatus | '';
  doctorId?: string;
}

/** Standard API envelope returned by the backend. */
export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  error: string | null;
}
