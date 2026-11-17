import type {
  AdminAppointmentQuery,
  Appointment,
  AppointmentStatus,
  AuthSession,
  BookingRequest,
  DailyStats,
  DayAvailability,
  Doctor,
  DoctorInput,
  DoctorQuery,
  DoctorSchedule,
  LoginInput,
  Notification,
  ProfileUpdate,
  Recommendation,
  RegisterInput,
  Review,
  User,
} from '@/types';

/**
 * Contract between the SPA and the backend. Implemented by the real HTTP
 * client (FastAPI/Node) and by the in-browser mock.
 */
export interface HealthcareApi {
  auth: {
    login(input: LoginInput): Promise<AuthSession>;
    register(input: RegisterInput): Promise<AuthSession>;
    me(): Promise<User>;
    updateProfile(update: ProfileUpdate): Promise<User>;
  };
  doctors: {
    list(query?: DoctorQuery): Promise<Doctor[]>;
    get(id: string): Promise<Doctor>;
    specializations(): Promise<string[]>;
    reviews(id: string): Promise<Review[]>;
    availability(id: string, date: string): Promise<DayAvailability>;
    recommendations(id: string, date: string): Promise<Recommendation[]>;
  };
  appointments: {
    book(request: BookingRequest): Promise<Appointment>;
    mine(): Promise<Appointment[]>;
    cancel(id: string): Promise<Appointment>;
  };
  notifications: {
    list(): Promise<Notification[]>;
    markAllRead(): Promise<void>;
  };
  admin: {
    appointments(query?: AdminAppointmentQuery): Promise<Appointment[]>;
    updateStatus(id: string, status: AppointmentStatus): Promise<Appointment>;
    doctors(): Promise<Doctor[]>;
    createDoctor(input: DoctorInput): Promise<Doctor>;
    updateDoctor(id: string, input: DoctorInput): Promise<Doctor>;
    getSchedule(doctorId: string): Promise<DoctorSchedule>;
    updateSchedule(schedule: DoctorSchedule): Promise<DoctorSchedule>;
    stats(date: string): Promise<DailyStats>;
  };
}
