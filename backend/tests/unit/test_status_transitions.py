"""Appointment lifecycle rules: PENDING -> CONFIRMED -> COMPLETED, cancellable until completed."""
import pytest

from app.models import AppointmentStatus as S
from app.services.booking import STATUS_TRANSITIONS

ALLOWED = [
    (S.PENDING, S.CONFIRMED),
    (S.PENDING, S.CANCELLED),
    (S.CONFIRMED, S.COMPLETED),
    (S.CONFIRMED, S.CANCELLED),
]
FORBIDDEN = [
    (S.PENDING, S.COMPLETED),  # must be confirmed first
    (S.PENDING, S.PENDING),
    (S.CONFIRMED, S.PENDING),  # no going backwards
    (S.CONFIRMED, S.CONFIRMED),
    (S.COMPLETED, S.CONFIRMED),
    (S.COMPLETED, S.CANCELLED),  # a finished visit cannot be cancelled
    (S.COMPLETED, S.PENDING),
    (S.CANCELLED, S.PENDING),  # cancellation is final: rebook instead
    (S.CANCELLED, S.CONFIRMED),
    (S.CANCELLED, S.COMPLETED),
]


@pytest.mark.parametrize(("current", "target"), ALLOWED, ids=lambda s: s.value.lower())
def test_allowed_moves(current: S, target: S) -> None:
    assert target in STATUS_TRANSITIONS[current]


@pytest.mark.parametrize(("current", "target"), FORBIDDEN, ids=lambda s: s.value.lower())
def test_forbidden_moves(current: S, target: S) -> None:
    assert target not in STATUS_TRANSITIONS[current]


def test_every_status_has_a_rule() -> None:
    assert set(STATUS_TRANSITIONS) == set(S)


@pytest.mark.parametrize("terminal", [S.COMPLETED, S.CANCELLED])
def test_terminal_states_have_no_exits(terminal: S) -> None:
    assert STATUS_TRANSITIONS[terminal] == set()


def test_the_table_is_exactly_the_documented_lifecycle() -> None:
    expected = {current: {t for c, t in ALLOWED if c == current} for current in S}
    assert STATUS_TRANSITIONS == expected
