from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from vouch_backend import api as api_module
from vouch_backend import auth
from vouch_backend.api import create_app
from vouch_backend.config import Settings
from vouch_backend.db import Database
from vouch_backend.models import Membership, MembershipRole, User
from vouch_backend.seed import ACME_ORG_ID, BETA_ORG_ID, MARKETER_USER_ID

SUBJECT = UUID("e1111111-1111-4111-8111-111111111111")
AUTH_ORIGIN = "http://127.0.0.1:54321"
TOKEN = "synthetic-access-token"


def test_fixture_database_cannot_target_hosted() -> None:
    with pytest.raises(ValueError, match="local persistence"):
        Settings(database_url="postgresql://postgres:unused@hosted.example:5432/postgres")


def test_openapi_declares_bearer_for_member_routes_not_health(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["SupabaseBearer"]["scheme"] == "bearer"
    assert schema["paths"]["/api/v1/me/workspaces"]["get"]["security"] == [{"SupabaseBearer": []}]
    assert "security" not in schema["paths"]["/health"]["get"]


def supabase_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://unused@127.0.0.1:54322/postgres",
        "environment": "test",
        "auth_mode": "supabase",
        "supabase_url": AUTH_ORIGIN,
        "supabase_publishable_key": "synthetic-publishable-key",
        "guest_rate_limit_key": "synthetic-auth-test-rate-limit-key-2026",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    # Exercise HTTP identity behavior against the isolated fixture DB. Auth HTTP is mocked;
    # separate local-Supabase integration tests prove real credentials and RLS behavior.
    client.app.state.settings = supabase_settings()
    with client.app.state.database.session_factory() as session:
        user = session.get(User, MARKETER_USER_ID)
        assert user is not None
        user.auth_subject = SUBJECT
        session.commit()
    return client


def mock_auth(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    client_type = httpx.Client

    def make_client(**kwargs: object) -> httpx.Client:
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return client_type(transport=httpx.MockTransport(handler), **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(auth.httpx, "Client", make_client)


def valid_auth_response(request: httpx.Request) -> httpx.Response:
    assert str(request.url) == f"{AUTH_ORIGIN}/auth/v1/user"
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert request.headers["apikey"] == "synthetic-publishable-key"
    return httpx.Response(
        200,
        json={
            "id": str(SUBJECT),
            "email": "admin@vouch.test",
            "user_metadata": {"roles": ["admin"], "organization_id": str(BETA_ORG_ID)},
        },
    )


def headers(*, organization: bool = True) -> dict[str, str]:
    result = {"Authorization": f"Bearer {TOKEN}"}
    if organization:
        result["X-Organization-Id"] = str(ACME_ORG_ID)
    return result


def test_verified_subject_discovers_all_active_workspaces_without_org(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_auth(monkeypatch, valid_auth_response)
    with authenticated_client.app.state.database.session_factory() as session:
        membership = Membership(
            id=uuid4(), organization_id=BETA_ORG_ID, user_id=MARKETER_USER_ID, active=True
        )
        session.add(membership)
        session.flush()
        session.add(
            MembershipRole(
                organization_id=BETA_ORG_ID, membership_id=membership.id, role="viewer"
            )
        )
        session.commit()
    result = authenticated_client.get("/api/v1/me/workspaces", headers=headers(organization=False))
    assert result.status_code == 200
    payload = result.json()
    assert {item["id"] for item in payload["items"]} == {str(ACME_ORG_ID), str(BETA_ORG_ID)}
    assert payload["user"]["id"] == str(MARKETER_USER_ID)
    assert payload["user"]["email"] == "marketer@vouch.test"
    acme = next(item for item in payload["items"] if item["id"] == str(ACME_ORG_ID))
    assert acme["roles"] == ["marketer"]


@pytest.mark.parametrize("status_code", [401, 403])
def test_invalid_or_expired_tokens_return_safe_unauthenticated_error(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    mock_auth(
        monkeypatch,
        lambda _request: httpx.Response(status_code, json={"message": "private-provider-detail"}),
    )
    result = authenticated_client.get("/api/v1/me/workspaces", headers=headers(organization=False))
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "AUTH_INVALID"
    assert "private-provider-detail" not in result.text


@pytest.mark.parametrize(
    "response",
    [httpx.Response(503), httpx.Response(302), httpx.Response(200, json={"id": "not-uuid"})],
)
def test_auth_unavailable_or_malformed_response_is_retryable(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> None:
    mock_auth(monkeypatch, lambda _request: response)
    result = authenticated_client.get("/api/v1/me/workspaces", headers=headers(organization=False))
    assert result.status_code == 503
    assert result.json()["error"]["retryable"] is True


def test_auth_network_failure_is_safe_and_retryable(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sensitive transport detail", request=request)

    mock_auth(monkeypatch, fail)
    result = authenticated_client.get("/api/v1/me/workspaces", headers=headers(organization=False))
    assert result.status_code == 503
    assert "sensitive transport detail" not in result.text


@pytest.mark.parametrize("name", ["X-Fixture-User", "X-Fixture-Roles"])
def test_authenticated_mode_rejects_fixture_identity_headers(
    authenticated_client: TestClient, name: str
) -> None:
    result = authenticated_client.get(
        "/api/v1/me/workspaces", headers={**headers(organization=False), name: "admin"}
    )
    assert result.status_code == 400
    assert result.json()["error"]["code"] == "FIXTURE_HEADERS_REJECTED"


@pytest.mark.parametrize("authorization", ["", "Basic synthetic", "Bearer", "Bearer a b"])
def test_bearer_is_required(authenticated_client: TestClient, authorization: str) -> None:
    result = authenticated_client.get(
        "/api/v1/me/workspaces", headers={"Authorization": authorization}
    )
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "AUTH_REQUIRED"


def test_organization_and_current_membership_are_required(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_auth(monkeypatch, valid_auth_response)
    missing = authenticated_client.get("/api/v1/products", headers=headers(organization=False))
    assert missing.status_code == 400
    assert authenticated_client.get("/api/v1/products", headers=headers()).status_code == 200
    with authenticated_client.app.state.database.session_factory() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.organization_id == ACME_ORG_ID, Membership.user_id == MARKETER_USER_ID
            )
        )
        assert membership is not None
        membership.active = False
        session.commit()
    denied = authenticated_client.get("/api/v1/products", headers=headers())
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "MEMBERSHIP_INACTIVE"
    workspaces = authenticated_client.get(
        "/api/v1/me/workspaces", headers=headers(organization=False)
    )
    assert workspaces.json()["items"] == []


def test_unknown_subject_cannot_claim_a_matching_email(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_auth(
        monkeypatch,
        lambda _request: httpx.Response(
            200, json={"id": str(uuid4()), "email": "marketer@vouch.test"}
        ),
    )
    result = authenticated_client.get("/api/v1/me/workspaces", headers=headers(organization=False))
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "USER_NOT_PROVISIONED"


def test_authenticated_content_put_requires_bearer(authenticated_client: TestClient) -> None:
    result = authenticated_client.put(
        f"/api/v1/uploads/{uuid4()}/content",
        headers={"X-Upload-Token": "synthetic-capability"},
        content=b"synthetic-content",
    )
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "AUTH_REQUIRED"


def test_cross_tenant_selection_is_denied(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_auth(monkeypatch, valid_auth_response)
    result = authenticated_client.get(
        "/api/v1/products",
        headers={**headers(), "X-Organization-Id": str(BETA_ORG_ID)},
    )
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "MEMBERSHIP_INACTIVE"


def test_role_revocation_takes_effect_on_next_request(
    authenticated_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_auth(monkeypatch, valid_auth_response)
    with authenticated_client.app.state.database.session_factory() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.organization_id == ACME_ORG_ID, Membership.user_id == MARKETER_USER_ID
            )
        )
        assert membership is not None
        role = session.scalar(
            select(MembershipRole).where(
                MembershipRole.membership_id == membership.id, MembershipRole.role == "marketer"
            )
        )
        assert role is not None
        session.delete(role)
        session.commit()
    workspaces = authenticated_client.get("/api/v1/me/workspaces", headers=headers())
    assert workspaces.status_code == 200
    assert workspaces.json()["items"][0]["roles"] == []


def test_authorization_header_is_allowed_in_browser_preflight(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.options(
        "/api/v1/products",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-organization-id",
        },
    )
    assert response.status_code == 200
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.parametrize(
    "overrides",
    [
        {"auth_mode": "invented"},
        {"database_url": "sqlite:///:memory:"},
        {"supabase_url": None},
        {"supabase_publishable_key": None},
        {"supabase_url": "http://untrusted.example"},
        {"supabase_url": "https://trusted.example/path"},
        {"supabase_url": "https://token@trusted.example"},
        {"supabase_url": "https://trusted.example?redirect=elsewhere"},
        {
            "guest_database_url": "postgresql+psycopg://guest@127.0.0.1:54322/postgres",
            "guest_rate_limit_key": "vouch-local-guest-rate-limit-key-2026",
        },
    ],
)
def test_invalid_auth_configuration_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        supabase_settings(**overrides)


@pytest.mark.parametrize(
    "guest_database_url",
    [
        "sqlite:///:memory:",
        "postgresql+psycopg://guest@remote.example:54322/postgres",
        "postgresql+psycopg://guest@127.0.0.1:64322/postgres",
        "postgresql+psycopg://guest@127.0.0.1:54322/other",
    ],
)
def test_guest_database_must_share_the_member_postgres_target(
    guest_database_url: str,
) -> None:
    with pytest.raises(ValueError):
        supabase_settings(guest_database_url=guest_database_url)


def test_guest_database_can_use_a_separate_redacted_login() -> None:
    guest_database_url = (
        "postgresql+psycopg://vouch_local_guest:sensitive-guest-password"
        "@127.0.0.1:54322/postgres"
    )
    settings = supabase_settings(guest_database_url=guest_database_url)

    assert settings.guest_database_url == guest_database_url
    assert "vouch_local_guest" not in repr(settings)
    assert "sensitive-guest-password" not in repr(settings)


def test_authenticated_guest_exchange_fails_closed_without_guest_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'guest-fail-closed.db').as_posix()}", "vouch")
    monkeypatch.setattr(api_module, "Database", lambda *_args, **_kwargs: database)
    app = create_app(supabase_settings())
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/v1/guest/exchange",
            headers={"Origin": "http://127.0.0.1:3000"},
            json={"invitation_secret": "synthetic-invitation-secret"},
        )

    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "GUEST_RUNTIME_UNAVAILABLE"
    assert error["message"] == "Creator access is not configured for this environment."
    assert error["retryable"] is True


def test_credentials_and_access_tokens_are_not_in_dataclass_repr() -> None:
    settings = supabase_settings(
        supabase_secret_key="sensitive-cleanup-key",
        guest_database_url=(
            "postgresql+psycopg://vouch_local_guest:sensitive-guest-password"
            "@127.0.0.1:54322/postgres"
        ),
    )
    assert "sensitive-cleanup-key" not in repr(settings)
    assert "synthetic-publishable-key" not in repr(settings)
    assert "sensitive-guest-password" not in repr(settings)
    assert "unused@" not in repr(settings)
    actor = auth.VerifiedActor(MARKETER_USER_ID, "a@vouch.test", "A", SUBJECT, TOKEN)
    assert TOKEN not in repr(actor)
