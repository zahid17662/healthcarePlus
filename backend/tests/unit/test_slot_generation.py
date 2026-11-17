"""Slot generation (services.admin.generate_slots) and the small scheduling helpers."""
from datetime import date, time

import pytest

from app.services.admin import generate_slots
from app.services.scheduling import add_minutes, weekday_index

MONDAY = 1


def starts(slots: list[tuple[int, time, bool]]) -> list[str]:
    return [t.strftime("%H:%M") for _, t, _ in slots]


class TestGenerateSlots:
    def test_fills_the_window_in_slot_sized_steps(self) -> None:
        slots = generate_slots([MONDAY], time(9), time(12), 30, None, None)
        assert starts(slots) == ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]

    def test_every_slot_is_available_without_a_break(self) -> None:
        slots = generate_slots([MONDAY], time(9), time(11), 30, None, None)
        assert all(available for _, _, available in slots)

    def test_slot_that_would_overrun_the_end_is_dropped(self) -> None:
        slots = generate_slots([MONDAY], time(9), time(10, 10), 30, None, None)
        assert starts(slots) == ["09:00", "09:30"]

    def test_window_shorter_than_one_slot_yields_nothing(self) -> None:
        assert generate_slots([MONDAY], time(9), time(9, 20), 30, None, None) == []

    def test_inverted_window_yields_nothing(self) -> None:
        assert generate_slots([MONDAY], time(17), time(9), 30, None, None) == []

    def test_break_makes_overlapping_slots_unavailable(self) -> None:
        slots = generate_slots([MONDAY], time(12), time(15), 30, time(13), time(14))
        availability = {t.strftime("%H:%M"): ok for _, t, ok in slots}
        assert availability == {
            "12:00": True,
            "12:30": True,
            "13:00": False,
            "13:30": False,
            "14:00": True,
            "14:30": True,
        }

    def test_break_that_cuts_a_slot_in_half_blocks_that_slot(self) -> None:
        slots = generate_slots([MONDAY], time(12), time(13, 30), 30, time(12, 15), time(12, 45))
        availability = {t.strftime("%H:%M"): ok for _, t, ok in slots}
        assert availability == {"12:00": False, "12:30": False, "13:00": True}

    def test_slot_ending_exactly_when_break_starts_is_still_available(self) -> None:
        slots = generate_slots([MONDAY], time(12), time(14), 30, time(13), time(14))
        availability = {t.strftime("%H:%M"): ok for _, t, ok in slots}
        assert availability["12:30"] is True
        assert availability["13:00"] is False

    def test_half_defined_break_is_ignored(self) -> None:
        slots = generate_slots([MONDAY], time(9), time(10), 30, time(9), None)
        assert all(ok for _, _, ok in slots)

    def test_each_working_day_gets_its_own_slots_sorted_by_day(self) -> None:
        slots = generate_slots([5, 1], time(9), time(10), 30, None, None)
        assert [(d, t.strftime("%H:%M")) for d, t, _ in slots] == [
            (1, "09:00"),
            (1, "09:30"),
            (5, "09:00"),
            (5, "09:30"),
        ]

    def test_duplicate_working_days_are_collapsed(self) -> None:
        slots = generate_slots([1, 1, 1], time(9), time(10), 30, None, None)
        assert len(slots) == 2

    def test_no_working_days_means_no_slots(self) -> None:
        assert generate_slots([], time(9), time(17), 30, None, None) == []

    @pytest.mark.parametrize(
        ("minutes", "expected_count"),
        [(10, 48), (15, 32), (20, 24), (30, 16), (45, 10), (60, 8), (120, 4)],
    )
    def test_slot_count_for_an_eight_hour_day(self, minutes: int, expected_count: int) -> None:
        assert len(generate_slots([MONDAY], time(9), time(17), minutes, None, None)) == expected_count


class TestAddMinutes:
    def test_adds_within_the_hour(self) -> None:
        assert add_minutes(time(9, 0), 30) == time(9, 30)

    def test_rolls_over_the_hour(self) -> None:
        assert add_minutes(time(9, 45), 30) == time(10, 15)

    def test_zero_minutes_is_identity(self) -> None:
        assert add_minutes(time(9, 5), 0) == time(9, 5)


class TestWeekdayIndex:
    """0 = Sunday ... 6 = Saturday, matching doctor_schedules.day_of_week."""

    @pytest.mark.parametrize(
        ("day", "expected"),
        [
            (date(2026, 11, 15), 0),  # Sunday
            (date(2026, 11, 16), 1),  # Monday
            (date(2026, 11, 17), 2),  # Tuesday
            (date(2026, 11, 20), 5),  # Friday
            (date(2026, 11, 21), 6),  # Saturday
        ],
        ids=["sun", "mon", "tue", "fri", "sat"],
    )
    def test_maps_dates_to_sunday_based_index(self, day: date, expected: int) -> None:
        assert weekday_index(day) == expected
