"""Who may call what: every route is checked for 401 (no/garbage token) and 403 (wrong role)."""
import uuid

import pytest
from httpx import AsyncClient

API = "/api/v1"
ID = str(uuid.uuid4())
DAY = "2030-01-15"

# (method, path, json body) for every endpoint that requires a signed-in user.
AUTHENTICATED = [
    ("GET", "/auth/me", None),
    ("PATCH", "/users/me", {}),
    ("GET", "/doctors", None),
    ("GET", "/doctors/specializations", None),
    ("GET", f"/doctors/{ID}", None),
    ("GET", f"/doctors/{ID}/reviews", None),
    ("GET", f"/doctors/{ID}/slots?date={DAY}", None),
    ("GET", f"/recommendations?doctorId={ID}&date={DAY}", None),
    ("GET", "/notifications", None),
    ("POST", "/notifications/read-all", None),
    ("PATCH", f"/appointments/{ID}/status", {"status": "CANCELLED"}),
    ("POST", "/appointments", {}),
    ("GET", "/appointments/me", None),
    *[(m, p, b) for m, p, b in [
        ("GET", f"/admin/appointments?date={DAY}", None),
        ("GET", "/admin/doctors", None),
        ("POST", "/admin/doctors", {}),
        ("PUT", f"/admin/doctors/{ID}", {}),
        ("GET", f"/admin/doctors/{ID}/schedule", None),
        ("PUT", f"/admin/doctors/{ID}/schedule", {}),
        ("GET", f"/admin/stats/daily?date={DAY}", None),
    ]],
]
ADMIN_ONLY = [row for row in AUTHENTICATED if row[1].startswith("/admin")]
PATIENT_ONLY = [("POST", "/appointments", {}), ("GET", "/appointments/me", None)]


def ids(rows: list[tuple[str, str, object]]) -> list[str]:
    return [f"{m} {p.split('?')[0].replace(ID, '{id}')}" for m, p, _ in rows]


async def call(client: AsyncClient, method: str, path: str, body: object, headers: dict | None = None):  # type: ignore[no-untyped-def]
    return await client.request(method, f"{API}{path}", json=body, headers=headers or {})


@pytest.mark.parametrize(("method", "path", "body"), AUTHENTICATED, ids=ids(AUTHENTICATED))
async def test_anonymous_callers_get_401(client: AsyncClient, method: str, path: str, body: object) -> None:
    assert (await call(client, method, path, body)).status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), AUTHENTICATED, ids=ids(AUTHENTICATED))
async def test_garbage_tokens_get_401(client: AsyncClient, method: str, path: str, body: object) -> None:
    headers = {"Authorization": "Bearer definitely.not.valid"}
    assert (await call(client, method, path, body, headers)).status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), ADMIN_ONLY, ids=ids(ADMIN_ONLY))
async def test_patients_are_forbidden_from_every_admin_route(
    client: AsyncClient, as_patient: dict, method: str, path: str, body: object
) -> None:
    response = await call(client, method, path, body, as_patient)
    assert response.status_code == 403
    assert response.json() == {"detail": "Administrator access required."}


@pytest.mark.parametrize(("method", "path", "body"), PATIENT_ONLY, ids=ids(PATIENT_ONLY))
async def test_admins_are_forbidden_from_patient_only_routes(
    client: AsyncClient, as_admin: dict, method: str, path: str, body: object
) -> None:
    assert (await call(client, method, path, body, as_admin)).status_code == 403


async def test_health_check_needs_no_token(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 200
