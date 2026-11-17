"""Request/response models. JSON is camelCase to match the TypeScript client."""
import uuid
from datetime import date, datetime, time
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    TypeAdapter,
    field_validator,
)
from pydantic.alias_generators import to_camel

from .models import AppointmentStatus, UserRole

HHMM = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
Password = Annotated[str, StringConstraints(min_length=8, max_length=72)]
_URL = TypeAdapter(AnyHttpUrl)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def hhmm(value: time) -> str:
    return value.strftime("%H:%M")


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


# ---------- auth / users ----------


class RegisterRequest(ApiModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
    email: EmailStr
    password: Password


class LoginRequest(ApiModel):
    # Plain string on purpose: login must work for every existing account regardless of the
    # stricter address policy applied at registration time.
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=72)]


class ProfileUpdate(ApiModel):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)] | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=32, pattern=r"^[+\d][\d\s-]{6,}$")] | None = None
    date_of_birth: date | None = None


class UserOut(ApiModel):
    id: uuid.UUID
    full_name: str
    email: str
    phone: str | None = None
    date_of_birth: date | None = None
    role: UserRole
    created_at: datetime


class AuthSessionOut(ApiModel):
    token: str
    user: UserOut


# ---------- doctors ----------


class DoctorIn(ApiModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
    specialization: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
    sub_specialties: list[Annotated[str, StringConstraints(max_length=60)]] = Field(default_factory=list, max_length=12)
    experience_years: int = Field(ge=0, le=70)
    bio: str = Field(default="", max_length=2000)
    hourly_rate: float = Field(gt=0, lt=100000)
    image_url: str = Field(default="", max_length=500)
    is_active: bool = True

    @field_validator("image_url")
    @classmethod
    def _http_url_only(cls, value: str) -> str:
        """Only http(s) URLs are stored, so a `javascript:` URL can never reach an <img>."""
        if value:
            _URL.validate_python(value)
        return value


class DoctorOut(ApiModel):
    id: uuid.UUID
    name: str
    specialization: str
    sub_specialties: list[str]
    experience_years: int
    bio: str
    hourly_rate: float
    image_url: str
    average_rating: float
    review_count: int
    is_active: bool


class ReviewOut(ApiModel):
    id: uuid.UUID
    doctor_id: uuid.UUID
    patient_name: str
    rating: int
    comment: str
    created_at: datetime


class TimeSlotOut(ApiModel):
    start_time: str
    end_time: str
    status: Literal["available", "booked", "blocked", "past"]


class DayAvailabilityOut(ApiModel):
    doctor_id: uuid.UUID
    date: date
    is_working_day: bool
    slots: list[TimeSlotOut]


class RecommendationOut(ApiModel):
    doctor: DoctorOut
    date: date
    start_time: str


class ScheduleIO(ApiModel):
    doctor_id: uuid.UUID
    working_days: list[Annotated[int, Field(ge=0, le=6)]] = Field(max_length=7)
    start_time: HHMM
    end_time: HHMM
    slot_minutes: int = Field(ge=10, le=120)
    break_start: HHMM | None = None
    break_end: HHMM | None = None
    blocked_dates: list[date] = Field(default_factory=list, max_length=366)


# ---------- appointments ----------


class BookingRequest(ApiModel):
    doctor_id: uuid.UUID
    date: date
    start_time: HHMM
    concerns: str = Field(default="", max_length=1000)
    symptoms: list[Annotated[str, StringConstraints(max_length=80)]] = Field(default_factory=list, max_length=20)


class StatusUpdate(ApiModel):
    status: AppointmentStatus


class AppointmentOut(ApiModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    doctor_id: uuid.UUID
    doctor_name: str
    specialization: str
    date: date
    start_time: str
    end_time: str
    concerns: str
    status: AppointmentStatus
    created_at: datetime
    updated_at: datetime


class NotificationOut(ApiModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message: str
    read: bool
    created_at: datetime


# ---------- admin stats ----------


class SpecialtyCount(ApiModel):
    specialization: str
    count: int


class DayCount(ApiModel):
    date: date
    bookings: int
    cancelled: int


class DailyStatsOut(ApiModel):
    date: date
    total_bookings: int
    confirmed: int
    pending: int
    completed: int
    cancelled: int
    cancellation_rate: float
    active_doctors: int
    by_specialty: list[SpecialtyCount]
    last7_days: list[DayCount]
