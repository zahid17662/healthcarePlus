from types import SimpleNamespace

import pytest

from app import ratelimit
from app.errors import AppError
from app.ratelimit import RateLimiter


def request_from(host: str | None) -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=host) if host else None)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Controllable monotonic clock: mutate clock[0] to move time."""
    now = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: now[0])
    return now


async def test_allows_requests_up_to_the_limit(clock: list[float]) -> None:
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        await limiter(request_from("10.0.0.1"))


async def test_blocks_the_request_over_the_limit_with_429(clock: list[float]) -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    await limiter(request_from("10.0.0.1"))
    await limiter(request_from("10.0.0.1"))
    with pytest.raises(AppError) as exc:
        await limiter(request_from("10.0.0.1"))
    assert exc.value.status_code == 429


async def test_limits_are_tracked_per_client(clock: list[float]) -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    await limiter(request_from("10.0.0.1"))
    await limiter(request_from("10.0.0.2"))  # a different client is unaffected


async def test_window_expiry_frees_the_client(clock: list[float]) -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    await limiter(request_from("10.0.0.1"))
    clock[0] += 61
    await limiter(request_from("10.0.0.1"))


async def test_requests_without_client_info_share_one_bucket(clock: list[float]) -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    await limiter(request_from(None))
    with pytest.raises(AppError):
        await limiter(request_from(None))


async def test_reset_clears_all_counters(clock: list[float]) -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    await limiter(request_from("10.0.0.1"))
    limiter.reset()
    await limiter(request_from("10.0.0.1"))
