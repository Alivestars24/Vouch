from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_workflow import create_campaign, create_submission

from vouch_backend.models import (
    GuestExchangeAttempt,
    GuestGrant,
    GuestSession,
    MediaAsset,
    Membership,
    MembershipRole,
    Submission,
)
from vouch_backend.seed import ACME_ORG_ID, MARKETER_USER_ID
from vouch_backend.service import utcnow

CREATOR_ORIGIN = "http://127.0.0.1:3000"
VIEWER_HEADERS = {
    "X-Organization-Id": str(ACME_ORG_ID),
    "X-Fixture-User": "viewer@vouch.test",
}


def invitation_secret(payload: dict[str, Any]) -> str:
    parsed = urlsplit(payload["invitation_url"])
    assert parsed.scheme == "http"
    assert parsed.netloc == "127.0.0.1:3000"
    assert parsed.path == "/creator"
    assert parsed.query == ""
    values = parse_qs(parsed.fragment, strict_parsing=True)
    assert set(values) == {"invite"}
    return values["invite"][0]


def issue_invitation(
    client: TestClient,
    marketer_headers: dict[str, str],
    *,
    issuer_headers: dict[str, str] | None = None,
    empty_submission: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    campaign = create_campaign(client, marketer_headers)
    submission = None if empty_submission else create_submission(client, marketer_headers, campaign)
    body: dict[str, Any] = {
        "creator_id": campaign["creator_ids"][0],
        "recovery_id": str(uuid4()),
    }
    if submission is not None:
        body["submission_id"] = submission["id"]
    response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=issuer_headers or marketer_headers,
        json=body,
    )
    assert response.status_code == 201, response.text
    return campaign, response.json(), submission


def exchange(client: TestClient, secret: str, *, origin: str = CREATOR_ORIGIN) -> Any:
    return client.post(
        "/api/v1/guest/exchange",
        headers={"Origin": origin},
        json={"invitation_secret": secret},
    )


def safe_denial(response: Any) -> tuple[int, str, str]:
    error = response.json()["error"]
    return response.status_code, error["code"], error["message"]


def test_issue_exchange_and_read_only_scoped_submission(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign, invitation, submission = issue_invitation(client, marketer_headers)
    assert submission is not None
    assert set(invitation) == {
        "id",
        "campaign_id",
        "creator_id",
        "submission_id",
        "allowed_actions",
        "expires_at",
        "invitation_url",
    }
    assert invitation["campaign_id"] == campaign["id"]
    assert invitation["creator_id"] == campaign["creator_ids"][0]
    assert invitation["submission_id"] == submission["id"]
    assert invitation["allowed_actions"] == [
        "read_submission",
        "upload_source",
        "submit_version",
    ]
    secret = invitation_secret(invitation)
    assert len(secret) >= 43

    issued = exchange(client, secret)
    assert issued.status_code == 200, issued.text
    assert set(issued.json()) == {"status", "expires_at"}
    assert issued.json()["status"] == "active"
    assert issued.headers["cache-control"] == "no-store"
    assert issued.headers["referrer-policy"] == "no-referrer"
    cookie = issued.headers["set-cookie"]
    assert "vouch_guest_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/v1/guest" in cookie
    assert "Secure" not in cookie  # Explicit loopback HTTP development exception.

    scoped = client.get("/api/v1/guest/submission")
    assert scoped.status_code == 200, scoped.text
    assert scoped.headers["cache-control"] == "no-store"
    payload = scoped.json()
    assert set(payload) == {
        "session_expires_at",
        "campaign",
        "creator",
        "submission",
        "allowed_actions",
        "feedback",
    }
    assert payload["campaign"] == {
        "name": "Synthetic launch",
        "market": "IN",
        "brand_name": "Acme Eyewear",
    }
    assert payload["creator"] == {
        "name": "Synthetic Creator",
        "handle": "@synthetic-creator",
    }
    assert payload["submission"]["review_state"] == "awaiting_brand_review"
    assert payload["submission"]["approved_version_no"] is None
    assert payload["submission"]["current_version"]["version_no"] == 1
    assert payload["submission"]["current_version"]["caption"] == (
        "New frames. Sponsored fixture draft."
    )
    assert UUID(payload["submission"]["current_version"]["consent_receipt_id"])
    assert payload["allowed_actions"] == [
        "read_submission",
        "upload_source",
        "submit_version",
    ]
    assert payload["feedback"] == []
    serialized = json.dumps(payload).lower()
    for forbidden in (
        "organization_id",
        "campaign_id",
        "creator_id",
        "submission_id",
        "asset_id",
        "check",
        "manifest",
        "finding",
        "budget",
        "member",
        "media_url",
    ):
        assert forbidden not in serialized

    with client.app.state.database.session_factory() as session:
        grant = session.scalar(select(GuestGrant))
        guest_session = session.scalar(select(GuestSession))
        assert grant is not None and guest_session is not None
        assert grant.invitation_secret_hash == hashlib.sha256(secret.encode()).hexdigest()
        assert secret not in repr(grant)
        session_cookie = issued.cookies["vouch_guest_session"]
        assert guest_session.session_secret_hash == hashlib.sha256(
            session_cookie.encode()
        ).hexdigest()
        assert session_cookie not in repr(guest_session)


def test_exchange_replay_tampering_and_revocation_share_safe_denial(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, invitation, _submission = issue_invitation(client, marketer_headers)
    secret = invitation_secret(invitation)
    accepted = exchange(client, secret)
    assert accepted.status_code == 200

    client.cookies.clear()
    replay = exchange(client, secret)
    invalid = exchange(client, "x" * 43)
    assert safe_denial(replay) == safe_denial(invalid)
    assert safe_denial(replay)[0] == 401

    client.cookies.set("vouch_guest_session", "tampered-session-secret", path="/api/v1/guest")
    tampered = client.get("/api/v1/guest/submission")
    assert safe_denial(tampered) == safe_denial(replay)

    client.cookies.clear()
    client.cookies.set(
        "vouch_guest_session", accepted.cookies["vouch_guest_session"], path="/api/v1/guest"
    )
    revoked = client.post(
        f"/api/v1/guest-invitations/{invitation['id']}/revoke",
        headers=marketer_headers,
    )
    assert revoked.status_code == 202, revoked.text
    assert revoked.json() == {"status": "revoked"}
    denied = client.get("/api/v1/guest/submission")
    assert safe_denial(denied) == safe_denial(replay)


def test_recovery_and_renewal_rotate_all_prior_guest_credentials(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    recovery_id = uuid4()
    payload = {
        "creator_id": campaign["creator_ids"][0],
        "submission_id": submission["id"],
        "recovery_id": str(recovery_id),
    }
    invitation_url = f"/api/v1/campaigns/{campaign['id']}/guest-invitations"

    first_response = client.post(invitation_url, headers=marketer_headers, json=payload)
    assert first_response.status_code == 201, first_response.text
    first = first_response.json()
    first_secret = invitation_secret(first)
    assert exchange(client, first_secret).status_code == 200
    first_session = client.cookies["vouch_guest_session"]
    client.cookies.clear()

    recovered_response = client.post(invitation_url, headers=marketer_headers, json=payload)
    assert recovered_response.status_code == 201, recovered_response.text
    recovered = recovered_response.json()
    recovered_secret = invitation_secret(recovered)
    assert recovered["id"] != first["id"]
    assert recovered_secret != first_secret
    assert exchange(client, first_secret).status_code == 401
    client.cookies.set("vouch_guest_session", first_session, path="/api/v1/guest")
    assert client.get("/api/v1/guest/submission").status_code == 401
    client.cookies.clear()

    assert exchange(client, recovered_secret).status_code == 200
    recovered_session = client.cookies["vouch_guest_session"]
    client.cookies.clear()
    renewed_response = client.post(
        f"/api/v1/guest-invitations/{first['id']}/renew",
        headers=marketer_headers,
    )
    assert renewed_response.status_code == 201, renewed_response.text
    renewed = renewed_response.json()
    renewed_secret = invitation_secret(renewed)
    assert renewed["id"] not in {first["id"], recovered["id"]}
    assert exchange(client, recovered_secret).status_code == 401
    client.cookies.set("vouch_guest_session", recovered_session, path="/api/v1/guest")
    assert client.get("/api/v1/guest/submission").status_code == 401
    client.cookies.clear()
    assert exchange(client, renewed_secret).status_code == 200

    with client.app.state.database.session_factory() as session:
        family = session.scalars(
            select(GuestGrant)
            .where(GuestGrant.issuance_recovery_id == recovery_id)
            .order_by(GuestGrant.created_at)
        ).all()
        assert len(family) == 3
        assert {grant.renewal_root_id for grant in family} == {UUID(first["id"])}
        assert sum(grant.revoked_at is None for grant in family) == 1


def test_issuer_authority_and_expiry_are_rechecked_on_every_guest_request(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, invitation, _submission = issue_invitation(client, marketer_headers)
    accepted = exchange(client, invitation_secret(invitation))
    assert accepted.status_code == 200
    assert client.get("/api/v1/guest/submission").status_code == 200

    with client.app.state.database.session_factory() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.organization_id == ACME_ORG_ID,
                Membership.user_id == MARKETER_USER_ID,
            )
        )
        assert membership is not None
        role = session.scalar(
            select(MembershipRole).where(
                MembershipRole.membership_id == membership.id,
                MembershipRole.role == "marketer",
            )
        )
        assert role is not None
        session.delete(role)
        session.commit()
    assert client.get("/api/v1/guest/submission").status_code == 401

    with client.app.state.database.session_factory() as session:
        role = MembershipRole(
            organization_id=ACME_ORG_ID,
            membership_id=membership.id,
            role="marketer",
        )
        session.add(role)
        guest_session = session.scalar(select(GuestSession))
        assert guest_session is not None
        guest_session.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert client.get("/api/v1/guest/submission").status_code == 401


def test_guest_context_fails_closed_after_current_source_expires(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, invitation, submission = issue_invitation(client, marketer_headers)
    assert submission is not None
    assert exchange(client, invitation_secret(invitation)).status_code == 200

    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(submission["versions"][0]["asset_id"]))
        assert asset is not None
        asset.retention_deadline = utcnow() - timedelta(seconds=1)
        session.commit()

    assert client.get("/api/v1/guest/submission").status_code == 401


def test_current_version_pointer_cannot_cross_submission_lineage(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    campaign, invitation, first = issue_invitation(client, marketer_headers)
    assert first is not None
    assert exchange(client, invitation_secret(invitation)).status_code == 200
    second = create_submission(client, marketer_headers, campaign)

    with client.app.state.database.session_factory() as session:
        first_submission = session.get(Submission, UUID(first["id"]))
        assert first_submission is not None
        first_submission.current_version_id = UUID(second["versions"][0]["id"])
        session.commit()

    assert client.get("/api/v1/guest/submission").status_code == 401


def test_issuer_matrix_roster_and_tenant_scope(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
    beta_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    payload = {
        "creator_id": campaign["creator_ids"][0],
        "submission_id": submission["id"],
        "recovery_id": str(uuid4()),
    }
    reviewer = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=reviewer_headers,
        json=payload,
    )
    assert reviewer.status_code == 201, reviewer.text
    empty_reviewer = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=reviewer_headers,
        json={
            "creator_id": campaign["creator_ids"][0],
            "recovery_id": str(uuid4()),
        },
    )
    assert empty_reviewer.status_code == 403
    viewer = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=VIEWER_HEADERS,
        json=payload,
    )
    assert viewer.status_code == 403
    cross_tenant = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=beta_headers,
        json=payload,
    )
    assert cross_tenant.status_code == 404
    wrong_creator = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer_headers,
        json={
            "creator_id": "20000000-0000-4000-8000-000000000003",
            "submission_id": submission["id"],
            "recovery_id": str(uuid4()),
        },
    )
    assert wrong_creator.status_code == 404

    empty_marketer = client.post(
        f"/api/v1/campaigns/{campaign['id']}/guest-invitations",
        headers=marketer_headers,
        json={
            "creator_id": campaign["creator_ids"][0],
            "recovery_id": str(uuid4()),
        },
    )
    assert empty_marketer.status_code == 201, empty_marketer.text


def test_exchange_origin_cors_and_durable_client_rate_limit(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, invitation, _submission = issue_invitation(client, marketer_headers)
    secret = invitation_secret(invitation)
    missing_origin = client.post(
        "/api/v1/guest/exchange", json={"invitation_secret": secret}
    )
    untrusted_origin = exchange(client, secret, origin="https://attacker.example")
    assert missing_origin.status_code == 403
    assert untrusted_origin.status_code == 403

    preflight = client.options(
        "/api/v1/guest/exchange",
        headers={
            "Origin": CREATOR_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == CREATOR_ORIGIN
    assert preflight.headers["access-control-allow-credentials"] == "true"

    for index in range(10):
        response = exchange(client, f"invalid-secret-{index:02d}".ljust(43, "x"))
        assert response.status_code == 401
    limited = exchange(client, secret)
    assert limited.status_code == 401
    with client.app.state.database.session_factory() as session:
        grant = session.scalar(
            select(GuestGrant).where(GuestGrant.id == UUID(invitation["id"]))
        )
        assert grant is not None
        assert grant.consumed_at is None
        assert len(session.scalars(select(GuestExchangeAttempt)).all()) == 10


def test_token_rate_limit_stops_recording_after_the_bound(
    client: TestClient,
) -> None:
    repeated_secret = "same-invalid-secret".ljust(43, "x")
    for _index in range(12):
        assert exchange(client, repeated_secret).status_code == 401

    token_digest = hashlib.sha256(repeated_secret.encode()).hexdigest()
    with client.app.state.database.session_factory() as session:
        attempts = session.scalars(
            select(GuestExchangeAttempt).where(
                GuestExchangeAttempt.token_digest == token_digest
            )
        ).all()
        assert len(attempts) == 5


def test_guest_routes_do_not_advertise_member_bearer_auth(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "security" not in schema["paths"]["/api/v1/guest/exchange"]["post"]
    assert "security" not in schema["paths"]["/api/v1/guest/submission"]["get"]
