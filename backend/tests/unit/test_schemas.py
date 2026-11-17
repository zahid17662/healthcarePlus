"""Request validation rules (Pydantic models in app/schemas.py) and error helpers."""
import uuid
from datetime import time

import pytest
from pydantic import ValidationError

from app.errors import AppError, conflict, not_found, unprocessable
from app.schemas import (
    BookingRequest,
    DoctorIn,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    ScheduleIO,
    StatusUpdate,
    hhmm,
    parse_hhmm,
)

DOCTOR = {"name": "Dr. Test Person", "specialization": "Cardiology", "experienceYears": 5, "hourlyRate": 50}
SCHEDULE = {
    "doctorId": str(uuid.uuid4()),
    "workingDays": [1, 2],
    "startTime": "09:00",
    "endTime": "17:00",
    "slotMinutes": 30,
}


class TestTimeStrings:
    @pytest.mark.parametrize("value", ["00:00", "09:30", "12:59", "23:59"])
    def test_valid_times_accepted(self, value: str) -> None:
        assert BookingRequest(doctorId=uuid.uuid4(), date="2030-01-01", startTime=value).start_time == value

    @pytest.mark.parametrize("value", ["9:30", "24:00", "12:60", "ab:cd", "09-30", "09:30:00", ""])
    def test_invalid_times_rejected(self, value: str) -> None:
        with pytest.raises(ValidationError):
            BookingRequest(doctorId=uuid.uuid4(), date="2030-01-01", startTime=value)

    def test_hhmm_and_parse_round_trip(self) -> None:
        assert hhmm(parse_hhmm("07:05")) == "07:05"
        assert parse_hhmm("23:59") == time(23, 59)


class TestRegisterRequest:
    def make(self, **over: object) -> RegisterRequest:
        data = {"fullName": "  Ada Lovelace ", "email": "ada@example.com", "password": "Passw0rd!"}
        return RegisterRequest(**{**data, **over})  # type: ignore[arg-type]

    def test_name_is_trimmed(self) -> None:
        assert self.make().full_name == "Ada Lovelace"

    @pytest.mark.parametrize("password", ["short7!", "x" * 73])
    def test_password_length_bounds(self, password: str) -> None:
        with pytest.raises(ValidationError):
            self.make(password=password)

    @pytest.mark.parametrize("password", ["12345678", "x" * 72])
    def test_password_length_edges_accepted(self, password: str) -> None:
        assert self.make(password=password)

    @pytest.mark.parametrize("email", ["not-an-email", "a@b", "@example.com", "a@example.test"])
    def test_bad_email_rejected(self, email: str) -> None:
        with pytest.raises(ValidationError):
            self.make(email=email)

    def test_single_character_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self.make(fullName="A")

    def test_snake_case_field_names_also_work(self) -> None:
        assert RegisterRequest(full_name="Ada L", email="ada@example.com", password="Passw0rd!")


class TestLoginRequest:
    def test_accepts_non_routable_emails_of_existing_accounts(self) -> None:
        assert LoginRequest(email="admin@medibook.local", password="x").email == "admin@medibook.local"

    def test_blank_password_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest(email="a@example.com", password="")


class TestBookingRequest:
    def test_concern_length_limit(self) -> None:
        base = {"doctorId": str(uuid.uuid4()), "date": "2030-01-01", "startTime": "09:00"}
        assert BookingRequest(**base, concerns="x" * 1000)
        with pytest.raises(ValidationError):
            BookingRequest(**base, concerns="x" * 1001)

    def test_camel_case_aliases(self) -> None:
        req = BookingRequest.model_validate(
            {"doctorId": str(uuid.uuid4()), "date": "2030-01-01", "startTime": "10:00", "concerns": "hi"}
        )
        assert req.start_time == "10:00"

    def test_too_many_symptoms_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BookingRequest(
                doctorId=uuid.uuid4(), date="2030-01-01", startTime="09:00", symptoms=["x"] * 21
            )

    def test_invalid_doctor_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BookingRequest(doctorId="nope", date="2030-01-01", startTime="09:00")


class TestStatusUpdate:
    def test_unknown_status_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StatusUpdate(status="DONE")

    @pytest.mark.parametrize("status", ["PENDING", "CONFIRMED", "COMPLETED", "CANCELLED"])
    def test_known_statuses_accepted(self, status: str) -> None:
        assert StatusUpdate(status=status).status.value == status

    def test_lowercase_is_not_accepted_on_the_wire(self) -> None:
        with pytest.raises(ValidationError):
            StatusUpdate(status="cancelled")


class TestDoctorIn:
    def make(self, **over: object) -> DoctorIn:
        return DoctorIn.model_validate({**DOCTOR, **over})

    def test_minimal_valid_doctor(self) -> None:
        doctor = self.make()
        assert doctor.image_url == "" and doctor.is_active is True

    @pytest.mark.parametrize(
        "url",
        ["javascript:alert(1)", "data:text/html,<script>1</script>", "ftp://x.example/a.png", "//evil.example/a.png"],
    )
    def test_non_http_image_urls_rejected(self, url: str) -> None:
        with pytest.raises(ValidationError):
            self.make(imageUrl=url)

    @pytest.mark.parametrize("url", ["https://cdn.example.com/a.jpg", "http://cdn.example.com/a.jpg", ""])
    def test_http_and_empty_image_urls_accepted(self, url: str) -> None:
        assert self.make(imageUrl=url).image_url == url

    @pytest.mark.parametrize("rate", [0, -5, 100000])
    def test_hourly_rate_bounds(self, rate: float) -> None:
        with pytest.raises(ValidationError):
            self.make(hourlyRate=rate)

    @pytest.mark.parametrize("field,value", [("name", "ab"), ("experienceYears", -1), ("experienceYears", 71)])
    def test_other_field_bounds(self, field: str, value: object) -> None:
        with pytest.raises(ValidationError):
            self.make(**{field: value})

    def test_at_most_twelve_sub_specialties(self) -> None:
        with pytest.raises(ValidationError):
            self.make(subSpecialties=[f"s{i}" for i in range(13)])


class TestScheduleIO:
    def make(self, **over: object) -> ScheduleIO:
        return ScheduleIO.model_validate({**SCHEDULE, **over})

    @pytest.mark.parametrize("minutes", [10, 30, 120])
    def test_slot_minutes_within_bounds(self, minutes: int) -> None:
        assert self.make(slotMinutes=minutes).slot_minutes == minutes

    @pytest.mark.parametrize("minutes", [0, 9, 121])
    def test_slot_minutes_out_of_bounds(self, minutes: int) -> None:
        with pytest.raises(ValidationError):
            self.make(slotMinutes=minutes)

    @pytest.mark.parametrize("days", [[7], [-1], [0, 1, 2, 3, 4, 5, 6, 0]])
    def test_bad_working_days(self, days: list[int]) -> None:
        with pytest.raises(ValidationError):
            self.make(workingDays=days)

    def test_bad_time_format(self) -> None:
        with pytest.raises(ValidationError):
            self.make(startTime="9am")

    def test_blocked_dates_parsed_as_dates(self) -> None:
        assert str(self.make(blockedDates=["2030-02-01"]).blocked_dates[0]) == "2030-02-01"


class TestProfileUpdate:
    @pytest.mark.parametrize("phone", ["+8801712345678", "01712 345678", "017-1234-5678"])
    def test_plausible_phone_numbers(self, phone: str) -> None:
        assert ProfileUpdate(phone=phone).phone == phone

    @pytest.mark.parametrize("phone", ["abc", "12", "+", "<script>"])
    def test_implausible_phone_numbers(self, phone: str) -> None:
        with pytest.raises(ValidationError):
            ProfileUpdate(phone=phone)

    def test_unset_fields_are_reported_as_unset(self) -> None:
        assert ProfileUpdate(fullName="New Name").model_dump(exclude_unset=True) == {"full_name": "New Name"}

    def test_role_cannot_be_smuggled_in(self) -> None:
        update = ProfileUpdate.model_validate({"fullName": "New Name", "role": "ADMIN"})
        assert "role" not in update.model_dump()


class TestErrorHelpers:
    @pytest.mark.parametrize(
        ("error", "status"),
        [(not_found("Doctor"), 404), (conflict("taken"), 409), (unprocessable("bad"), 422)],
    )
    def test_status_codes(self, error: AppError, status: int) -> None:
        assert error.status_code == status

    def test_not_found_message_names_the_resource(self) -> None:
        assert not_found("Doctor").message == "Doctor not found."
