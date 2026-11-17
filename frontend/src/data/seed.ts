import type { Doctor, DoctorSchedule, Review, Weekday } from '@/types';

/**
 * Demo fixtures for the in-browser MOCK API only (VITE_API_URL empty).
 * These accounts never exist on a real backend.
 */
export const DEMO_ACCOUNTS = [
  { id: 'u-admin', fullName: 'Hospital Admin', email: 'admin@medibook.test', password: 'Admin@123', role: 'admin' as const },
  { id: 'u-patient', fullName: 'Demo Patient', email: 'patient@medibook.test', password: 'Patient@123', role: 'patient' as const },
];

export const SPECIALIZATIONS = [
  'Cardiology',
  'Dermatology',
  'Neurology',
  'Pediatrics',
  'Orthopedics',
  'General Medicine',
] as const;

const portrait = (gender: 'men' | 'women', n: number): string => `https://randomuser.me/api/portraits/${gender}/${n}.jpg`;

export const SEED_DOCTORS: Doctor[] = [
  {
    id: 'd-1', name: 'Dr. Sarah Ahmed', specialization: 'Cardiology',
    subSpecialties: ['Heart failure', 'Hypertension', 'Echocardiography'],
    experienceYears: 14, hourlyRate: 120, imageUrl: portrait('women', 44), averageRating: 4.7, reviewCount: 3, isActive: true,
    bio: 'Consultant cardiologist focused on preventive cardiology and long-term heart failure management.',
  },
  {
    id: 'd-2', name: 'Dr. Imran Hossain', specialization: 'Cardiology',
    subSpecialties: ['Arrhythmia', 'Pacemakers', 'Chest pain clinic'],
    experienceYears: 9, hourlyRate: 95, imageUrl: portrait('men', 32), averageRating: 4.5, reviewCount: 2, isActive: true,
    bio: 'Electrophysiology-trained cardiologist treating palpitations, arrhythmias and device follow-ups.',
  },
  {
    id: 'd-3', name: 'Dr. Nadia Rahman', specialization: 'Dermatology',
    subSpecialties: ['Acne', 'Eczema', 'Cosmetic dermatology'],
    experienceYears: 11, hourlyRate: 80, imageUrl: portrait('women', 65), averageRating: 5, reviewCount: 2, isActive: true,
    bio: 'Treats chronic skin conditions with an evidence-based, patient-friendly approach.',
  },
  {
    id: 'd-4', name: 'Dr. Arif Chowdhury', specialization: 'Neurology',
    subSpecialties: ['Migraine', 'Epilepsy', 'Stroke rehab'],
    experienceYears: 17, hourlyRate: 140, imageUrl: portrait('men', 52), averageRating: 4.5, reviewCount: 2, isActive: true,
    bio: 'Senior neurologist with a special interest in headache disorders and seizure management.',
  },
  {
    id: 'd-5', name: 'Dr. Farhana Kabir', specialization: 'Pediatrics',
    subSpecialties: ['Newborn care', 'Vaccination', 'Childhood asthma'],
    experienceYears: 8, hourlyRate: 70, imageUrl: portrait('women', 26), averageRating: 5, reviewCount: 2, isActive: true,
    bio: 'Gentle, family-centred paediatric care from newborns to teenagers.',
  },
  {
    id: 'd-6', name: 'Dr. Tanvir Alam', specialization: 'Orthopedics',
    subSpecialties: ['Sports injuries', 'Knee & hip', 'Arthroscopy'],
    experienceYears: 12, hourlyRate: 110, imageUrl: portrait('men', 41), averageRating: 4, reviewCount: 1, isActive: true,
    bio: 'Orthopaedic surgeon helping patients return to activity after joint and sports injuries.',
  },
  {
    id: 'd-7', name: 'Dr. Mahmud Karim', specialization: 'General Medicine',
    subSpecialties: ['Diabetes', 'Fever clinic', 'Health check-ups'],
    experienceYears: 6, hourlyRate: 50, imageUrl: portrait('men', 75), averageRating: 4, reviewCount: 1, isActive: true,
    bio: 'Primary-care physician for everyday illnesses, chronic disease follow-up and annual check-ups.',
  },
  {
    id: 'd-8', name: 'Dr. Lamia Sultana', specialization: 'Dermatology',
    subSpecialties: ['Psoriasis', 'Hair loss', 'Skin allergy'],
    experienceYears: 7, hourlyRate: 65, imageUrl: portrait('women', 12), averageRating: 5, reviewCount: 1, isActive: true,
    bio: 'Dermatologist focused on autoimmune skin disease and hair and scalp disorders.',
  },
];

const WEEKDAYS: Weekday[] = [0, 1, 2, 3, 4];
const ALT_DAYS: Weekday[] = [1, 3, 5, 6];

export const SEED_SCHEDULES: DoctorSchedule[] = SEED_DOCTORS.map((d, i) => ({
  doctorId: d.id,
  workingDays: i % 2 === 0 ? WEEKDAYS : ALT_DAYS,
  startTime: i % 3 === 0 ? '09:00' : '10:00',
  endTime: i % 3 === 0 ? '17:00' : '16:00',
  slotMinutes: 30,
  breakStart: '13:00',
  breakEnd: '14:00',
  blockedDates: [],
}));

export const SEED_REVIEWS: Review[] = [
  { id: 'r-1', doctorId: 'd-1', patientName: 'Rafiq U.', rating: 5, comment: 'Explained my echo results clearly and adjusted my meds. Felt genuinely heard.', createdAt: '2026-09-02T10:00:00Z' },
  { id: 'r-2', doctorId: 'd-1', patientName: 'Tania M.', rating: 5, comment: 'Very thorough and calm. Follow-up plan was easy to understand.', createdAt: '2026-09-21T10:00:00Z' },
  { id: 'r-3', doctorId: 'd-1', patientName: 'Kamal H.', rating: 4, comment: 'Great doctor, slight wait at the clinic.', createdAt: '2026-10-11T10:00:00Z' },
  { id: 'r-4', doctorId: 'd-2', patientName: 'Selina P.', rating: 5, comment: 'Finally found the cause of my palpitations.', createdAt: '2026-08-14T10:00:00Z' },
  { id: 'r-5', doctorId: 'd-2', patientName: 'Jamil R.', rating: 4, comment: 'Knowledgeable and quick.', createdAt: '2026-10-01T10:00:00Z' },
  { id: 'r-6', doctorId: 'd-3', patientName: 'Mitu A.', rating: 5, comment: 'My eczema is under control for the first time in years.', createdAt: '2026-09-09T10:00:00Z' },
  { id: 'r-7', doctorId: 'd-3', patientName: 'Sabbir K.', rating: 5, comment: 'Friendly, practical advice.', createdAt: '2026-10-18T10:00:00Z' },
  { id: 'r-8', doctorId: 'd-4', patientName: 'Nasrin J.', rating: 5, comment: 'Migraine plan has cut my attacks in half.', createdAt: '2026-07-30T10:00:00Z' },
  { id: 'r-9', doctorId: 'd-4', patientName: 'Habib S.', rating: 4, comment: 'Excellent expertise, busy schedule.', createdAt: '2026-09-27T10:00:00Z' },
  { id: 'r-10', doctorId: 'd-5', patientName: 'Ruma D.', rating: 5, comment: 'My kids actually like visiting her!', createdAt: '2026-10-05T10:00:00Z' },
  { id: 'r-11', doctorId: 'd-5', patientName: 'Arman B.', rating: 5, comment: 'Patient and reassuring with new parents.', createdAt: '2026-10-22T10:00:00Z' },
  { id: 'r-12', doctorId: 'd-6', patientName: 'Fahim Z.', rating: 4, comment: 'Back to football after my ACL rehab.', createdAt: '2026-08-19T10:00:00Z' },
  { id: 'r-13', doctorId: 'd-7', patientName: 'Shila N.', rating: 4, comment: 'Good general check-up, clear diet advice.', createdAt: '2026-09-15T10:00:00Z' },
  { id: 'r-14', doctorId: 'd-8', patientName: 'Pinky L.', rating: 5, comment: 'Helped a lot with my scalp psoriasis.', createdAt: '2026-10-08T10:00:00Z' },
];
