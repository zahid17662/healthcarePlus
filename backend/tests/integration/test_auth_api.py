"""Registration, login, profile and rate limiting through the real HTTP stack."""
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from testkit.factories import TEST_PASSWORD, auth_header, make_user, unique

from app.models import User, UserRole

API = "/api/v1"
BAD_CREDENTIALS = "Incorrect email or password."


def new_email() -> str:
    return f"{unique('reg')}@example.com"


async def register(client: AsyncClient, **over: object):  # type: ignore[no-untyped-def]
    body = {"fullName": "New Person", "email": new_email(), "password": "Passw0rd!x"}
    body.update(over)
    return await client.post(f"{API}/auth/register", json=body)


class TestRegister:
    async def test_creates_a_patient_and_returns_a_working_token(self, client: AsyncClient) -> None:
        response = await register(client, fullName="  Grace Hopper ")
        assert response.status_code == 201
        body = response.json()
        assert body["user"]["role"] == "PATIENT"
        assert body["user"]["fullName"] == "Grace Hopper"
        me = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
        assert me.status_code == 200 and me.json()["id"] == body["user"]["id"]

    async def test_response_never_contains_password_material(self, client: AsyncClient) -> None:
        response = await register(client, password="Sup3r-Secret-Pw")
        assert "Sup3r-Secret-Pw" not in response.text
        assert "passwordHash" not in response.text and "password_hash" not in response.text

    async def test_password_is_stored_as_a_bcrypt_hash(self, client: AsyncClient, db: AsyncSession) -> None:
        email = new_email()
        await register(client, email=email, password="Plain-Text-Pw1")
        stored = (await db.execute(select(User).where(User.email == email))).scalar_one()
        assert stored.password_hash.startswith("$2") and "Plain-Text-Pw1" not in stored.password_hash

    async def test_email_is_normalised_to_lowercase(self, client: AsyncClient) -> None:
        response = await register(client, email=f"MiXeD-{unique('c')}@Example.com")
        assert response.json()["user"]["email"] == response.json()["user"]["email"].lower()

    async def test_duplicate_email_is_409(self, client: AsyncClient) -> None:
        email = new_email()
        assert (await register(client, email=email)).status_code == 201
        duplicate = await register(client, email=email)
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "An account with this email already exists."

    async def test_duplicate_check_ignores_case(self, client: AsyncClient) -> None:
        email = new_email()
        await register(client, email=email)
        assert (await register(client, email=email.upper().replace("@EXAMPLE.COM", "@example.com"))).status_code == 409

    async def test_cannot_self_assign_the_admin_role(self, client: AsyncClient) -> None:
        response = await register(client, role="ADMIN")
        assert response.status_code == 201
        assert response.json()["user"]["role"] == "PATIENT"

    async def test_rejects_weak_invalid_or_missing_input(self, client: AsyncClient) -> None:
        assert (await register(client, password="short")).status_code == 422
        assert (await register(client, email="not-an-email")).status_code == 422
        assert (await register(client, fullName="A")).status_code == 422
        assert (await client.post(f"{API}/auth/register", json={})).status_code == 422


class TestLogin:
    async def test_valid_credentials_return_a_token_and_the_user(self, client: AsyncClient) -> None:
        user = await make_user()
        response = await client.post(f"{API}/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
        assert response.status_code == 200
        assert response.json()["user"]["id"] == str(user.id)
        assert response.json()["token"]

    async def test_wrong_password_and_unknown_email_give_the_same_401(self, client: AsyncClient) -> None:
        user = await make_user()
        wrong_pw = await client.post(f"{API}/auth/login", json={"email": user.email, "password": "nope-nope-1"})
        no_user = await client.post(f"{API}/auth/login", json={"email": new_email(), "password": "nope-nope-1"})
        assert wrong_pw.status_code == no_user.status_code == 401
        assert wrong_pw.json() == no_user.json() == {"detail": BAD_CREDENTIALS}

    async def test_email_match_is_case_insensitive(self, client: AsyncClient) -> None:
        user = await make_user()
        response = await client.post(f"{API}/auth/login", json={"email": user.email.upper(), "password": TEST_PASSWORD})
        assert response.status_code == 200

    async def test_accounts_with_non_routable_email_domains_can_still_log_in(self, client: AsyncClient) -> None:
        """e.g. the seeded admin@medibook.local: login must not re-apply registration's email policy."""
        user = await make_user(UserRole.ADMIN, email=f"{unique('boss')}@medibook.local")
        response = await client.post(f"{API}/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
        assert response.status_code == 200 and response.json()["user"]["role"] == "ADMIN"

    async def test_missing_fields_are_422(self, client: AsyncClient) -> None:
        assert (await client.post(f"{API}/auth/login", json={"email": "a@example.com"})).status_code == 422


class TestCurrentUser:
    async def test_requires_a_token(self, client: AsyncClient) -> None:
        response = await client.get(f"{API}/auth/me")
        assert response.status_code == 401 and response.json() == {"detail": "Authentication required."}

    async def test_rejects_a_garbage_token(self, client: AsyncClient) -> None:
        response = await client.get(f"{API}/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
        assert response.status_code == 401

    async def test_returns_the_callers_profile(self, client: AsyncClient, patient: User, as_patient: dict) -> None:
        body = (await client.get(f"{API}/auth/me", headers=as_patient)).json()
        assert body["email"] == patient.email and body["role"] == "PATIENT"

    async def test_token_of_a_deleted_user_stops_working(
        self, client: AsyncClient, db: AsyncSession
    ) -> None:
        doomed = await make_user()
        headers = auth_header(doomed)
        assert (await client.get(f"{API}/auth/me", headers=headers)).status_code == 200
        await db.delete(await db.get(User, doomed.id))
        await db.commit()
        assert (await client.get(f"{API}/auth/me", headers=headers)).status_code == 401


class TestProfileUpdate:
    async def test_updates_name_phone_and_birth_date(self, client: AsyncClient, as_patient: dict) -> None:
        response = await client.patch(
            f"{API}/users/me",
            headers=as_patient,
            json={"fullName": "  Renamed Person ", "phone": "+8801712345678", "dateOfBirth": "1990-05-17"},
        )
        assert response.status_code == 200
        body = response.json()
        assert (body["fullName"], body["phone"], body["dateOfBirth"]) == ("Renamed Person", "+8801712345678", "1990-05-17")
        assert (await client.get(f"{API}/auth/me", headers=as_patient)).json()["phone"] == "+8801712345678"

    async def test_partial_update_leaves_other_fields_alone(self, client: AsyncClient, as_patient: dict) -> None:
        await client.patch(f"{API}/users/me", headers=as_patient, json={"phone": "01712345678"})
        after = (await client.patch(f"{API}/users/me", headers=as_patient, json={"fullName": "Only Name"})).json()
        assert after["phone"] == "01712345678" and after["fullName"] == "Only Name"

    async def test_null_name_is_ignored_not_stored(self, client: AsyncClient, patient: User, as_patient: dict) -> None:
        response = await client.patch(f"{API}/users/me", headers=as_patient, json={"fullName": None})
        assert response.status_code == 200 and response.json()["fullName"] == patient.full_name

    async def test_invalid_phone_is_422(self, client: AsyncClient, as_patient: dict) -> None:
        assert (await client.patch(f"{API}/users/me", headers=as_patient, json={"phone": "abc"})).status_code == 422

    async def test_role_and_email_cannot_be_changed(self, client: AsyncClient, patient: User, as_patient: dict) -> None:
        await client.patch(
            f"{API}/users/me", headers=as_patient, json={"role": "ADMIN", "email": "hijack@example.com"}
        )
        me = (await client.get(f"{API}/auth/me", headers=as_patient)).json()
        assert me["role"] == "PATIENT" and me["email"] == patient.email

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.patch(f"{API}/users/me", json={"fullName": "X Y"})).status_code == 401


class TestAuthRateLimit:
    async def test_eleventh_attempt_in_a_minute_is_429(self, client: AsyncClient) -> None:
        for _ in range(10):  # invalid bodies: counted by the limiter, no bcrypt cost
            assert (await client.post(f"{API}/auth/login", json={})).status_code == 422
        blocked = await client.post(f"{API}/auth/login", json={})
        assert blocked.status_code == 429
        assert "Too many attempts" in blocked.json()["detail"]

    async def test_login_and_register_share_one_budget(self, client: AsyncClient) -> None:
        for _ in range(5):
            await client.post(f"{API}/auth/login", json={})
            await client.post(f"{API}/auth/register", json={})
        assert (await client.post(f"{API}/auth/register", json={})).status_code == 429
        assert (await client.post(f"{API}/auth/login", json={})).status_code == 429

    async def test_limit_is_per_client_address(self, client: AsyncClient) -> None:
        from app.main import app

        for _ in range(11):
            await client.post(f"{API}/auth/login", json={})
        transport = ASGITransport(app=app, client=("203.0.113.77", 4000))
        async with AsyncClient(transport=transport, base_url="http://test") as other:
            assert (await other.post(f"{API}/auth/login", json={})).status_code == 422  # not 429

    async def test_other_endpoints_are_not_limited_by_the_auth_budget(
        self, client: AsyncClient, as_patient: dict
    ) -> None:
        for _ in range(11):
            await client.post(f"{API}/auth/login", json={})
        assert (await client.get(f"{API}/auth/me", headers=as_patient)).status_code == 200
