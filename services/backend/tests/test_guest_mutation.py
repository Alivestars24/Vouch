from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_guest_portal import (
    CREATOR_ORIGIN,
    exchange,
    invitation_secret,
    issue_invitation,
)
from test_workflow import MP4

from vouch_backend.models import (
    AuditEvent,
    ConsentReceipt,
    DeletionRequest,
    GuestCommand,
    GuestGrant,
    GuestSession,
    MediaAsset,
    Membership,
    MembershipRole,
    SubmissionVersion,
)
from vouch_backend.seed import ACME_ORG_ID, MARKETER_USER_ID


def _origin_headers(**extra: str) -> dict[str, str]:
    return {"Origin": CREATOR_ORIGIN, **extra}


def _notice(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/v1/guest/notices/campaign-check")
    assert response.status_code == 200, response.text
    return response.json()


def _intent_body(notice: dict[str, Any], *, filename: str = "creator-draft.mp4") -> dict[str, Any]:
    return {
        "filename": filename,
        "content_type": "video/mp4",
        "byte_size": len(MP4),
        "rights_attested": True,
        "notice_version": notice["version"],
        "notice_acknowledged": True,
        "purpose": "campaign_check",
    }


def _create_intent(
    client: TestClient,
    notice: dict[str, Any],
    key: str,
    *,
    filename: str = "creator-draft.mp4",
) -> Any:
    return client.post(
        "/api/v1/guest/uploads",
        headers=_origin_headers(**{"Idempotency-Key": key}),
        json=_intent_body(notice, filename=filename),
    )


def _put(client: TestClient, intent: dict[str, Any], body: bytes = MP4) -> Any:
    return client.put(
        intent["content_url"],
        headers=_origin_headers(
            **{
                "Content-Type": "video/mp4",
                "X-Upload-Token": intent["upload_token"],
            }
        ),
        content=body,
    )


def _finalize(client: TestClient, intent: dict[str, Any]) -> Any:
    return client.post(
        intent["finalize_url"],
        headers=_origin_headers(),
        json={"finalize_token": intent["finalize_token"]},
    )


def test_guest_initial_draft_is_idempotent_and_truthfully_attributed(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, invitation, submission = issue_invitation(
        client, marketer_headers, empty_submission=True
    )
    assert submission is None
    assert invitation["allowed_actions"] == [
        "read_submission",
        "upload_source",
        "submit_version",
    ]
    assert exchange(client, invitation_secret(invitation)).status_code == 200
    notice = _notice(client)
    assert notice["version"].startswith("creator-campaign-check-")
    assert "workspace member" not in notice["body"].lower()

    first = _create_intent(client, notice, "initial-source")
    assert first.status_code == 201, first.text
    intent = first.json()
    assert set(intent) == {
        "upload_id",
        "content_url",
        "upload_token",
        "finalize_url",
        "finalize_token",
        "required_header",
        "max_bytes",
        "expires_at",
        "authorization_status",
        "consent_receipt",
    }
    assert set(intent["consent_receipt"]) == {
        "id",
        "purpose",
        "notice_version",
        "notice_hash",
        "accepted_at",
    }
    identical_intent = _create_intent(client, notice, "initial-source")
    assert identical_intent.status_code == 201
    assert identical_intent.json() == intent

    stored = _put(client, intent)
    assert stored.status_code == 200, stored.text
    assert stored.json() == {
        "upload_id": intent["upload_id"],
        "status": "content_uploaded",
        "received_bytes": len(MP4),
    }
    assert _put(client, intent).json() == stored.json()
    finalized = _finalize(client, intent)
    assert finalized.status_code == 200, finalized.text
    assert finalized.json() == {"asset_id": intent["upload_id"], "status": "validated"}
    assert _finalize(client, intent).json() == finalized.json()

    # A lost finalize response makes the browser replay the same bounded command chain.
    # The already-validated source must acknowledge the same bytes without reopening it.
    replayed_store = _put(client, intent)
    assert replayed_store.status_code == 200, replayed_store.text
    assert replayed_store.json() == stored.json()
    changed_replay = _put(client, intent, MP4[:-1] + b"x")
    assert changed_replay.status_code == 409
    assert changed_replay.json()["error"]["code"] == "UPLOAD_CONTENT_CONFLICT"

    version_body = {
        "asset_id": intent["upload_id"],
        "caption": "Creator-owned first draft.",
        "expected_current_version_id": None,
    }
    version = client.post(
        "/api/v1/guest/submission-versions",
        headers=_origin_headers(**{"Idempotency-Key": "initial-version"}),
        json=version_body,
    )
    assert version.status_code == 201, version.text
    assert set(version.json()) == {"id", "version_no", "caption", "created_at"}
    assert version.json()["version_no"] == 1
    identical_version = client.post(
        "/api/v1/guest/submission-versions",
        headers=_origin_headers(**{"Idempotency-Key": "initial-version"}),
        json=version_body,
    )
    assert identical_version.status_code == 201
    assert identical_version.json() == version.json()
    scoped = client.get("/api/v1/guest/submission")
    assert scoped.status_code == 200
    assert scoped.json()["submission"]["current_version"]["caption"] == version_body["caption"]

    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        receipt = session.get(ConsentReceipt, UUID(intent["consent_receipt"]["id"]))
        stored_version = session.get(SubmissionVersion, UUID(version.json()["id"]))
        guest_session = session.scalar(select(GuestSession))
        assert asset and receipt and stored_version and guest_session
        assert asset.uploader_user_id is None
        assert asset.uploader_guest_session_id == guest_session.id
        assert receipt.actor_user_id is None
        assert receipt.actor_guest_session_id == guest_session.id
        assert stored_version.uploader_user_id is None
        assert stored_version.uploader_guest_session_id == guest_session.id
        assert asset.upload_token_hash == hashlib.sha256(
            intent["upload_token"].encode()
        ).hexdigest()
        assert asset.finalize_token_hash == hashlib.sha256(
            intent["finalize_token"].encode()
        ).hexdigest()
        assert session.scalar(select(func.count()).select_from(GuestCommand)) == 2
        guest_events = session.scalars(
            select(AuditEvent).where(AuditEvent.actor_kind == "guest")
        ).all()
        assert guest_events
        assert all(event.actor_user_id is None for event in guest_events)
        assert all(event.actor_guest_session_id == guest_session.id for event in guest_events)

    # A guest cookie is never member authority and cannot start Check or approve anything.
    assert client.get("/api/v1/campaigns").status_code == 401


def test_guest_notice_origin_idempotency_and_atomic_grant_quota(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, invitation, _submission = issue_invitation(
        client, marketer_headers, empty_submission=True
    )
    assert exchange(client, invitation_secret(invitation)).status_code == 200
    notice = _notice(client)
    body = _intent_body(notice)

    missing_notice = {key: value for key, value in body.items() if key != "notice_acknowledged"}
    assert client.post(
        "/api/v1/guest/uploads",
        headers=_origin_headers(**{"Idempotency-Key": "missing-notice"}),
        json=missing_notice,
    ).status_code == 422
    stale = client.post(
        "/api/v1/guest/uploads",
        headers=_origin_headers(**{"Idempotency-Key": "stale-notice"}),
        json={**body, "notice_version": "member-or-stale-notice"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "NOTICE_VERSION_STALE"
    assert client.post(
        "/api/v1/guest/uploads",
        headers={"Idempotency-Key": "missing-origin"},
        json=body,
    ).status_code == 403
    missing_key = client.post(
        "/api/v1/guest/uploads",
        headers=_origin_headers(),
        json=body,
    )
    assert missing_key.status_code == 422
    assert missing_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    intents = []
    for index in range(5):
        response = _create_intent(client, notice, f"source-{index}", filename=f"{index}.mp4")
        assert response.status_code == 201, response.text
        intents.append(response.json())
    assert _create_intent(client, notice, "source-0", filename="0.mp4").json() == intents[0]
    reused = _create_intent(client, notice, "source-0", filename="changed.mp4")
    assert reused.status_code == 409
    assert reused.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    exhausted = _create_intent(client, notice, "source-5", filename="5.mp4")
    assert exhausted.status_code == 409
    assert exhausted.json()["error"]["code"] == "GUEST_UPLOAD_QUOTA_EXCEEDED"

    with client.app.state.database.session_factory() as session:
        grant = session.get(GuestGrant, UUID(invitation["id"]))
        assert grant and grant.source_count == 5
        assert grant.reserved_bytes == 5 * len(MP4)
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 5
        assert session.scalar(select(func.count()).select_from(GuestCommand)) == 5


def test_guest_mutations_deny_cross_scope_legacy_grants_and_lost_issuer_authority(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, first_invitation, _submission = issue_invitation(
        client, marketer_headers, empty_submission=True
    )
    assert exchange(client, invitation_secret(first_invitation)).status_code == 200
    first_cookie = client.cookies["vouch_guest_session"]
    notice = _notice(client)
    first_intent_response = _create_intent(client, notice, "first-scope")
    assert first_intent_response.status_code == 201
    first_intent = first_intent_response.json()

    _other_campaign, second_invitation, _other_submission = issue_invitation(
        client, marketer_headers, empty_submission=True
    )
    client.cookies.clear()
    assert exchange(client, invitation_secret(second_invitation)).status_code == 200
    cross_scope = _put(client, first_intent)
    assert cross_scope.status_code == 404

    client.cookies.clear()
    client.cookies.set("vouch_guest_session", first_cookie, path="/api/v1/guest")
    with client.app.state.database.session_factory() as session:
        grant = session.get(GuestGrant, UUID(first_invitation["id"]))
        assert grant
        grant.allowed_actions = ["read_submission"]
        session.commit()
    assert client.get("/api/v1/guest/submission").status_code == 200
    assert client.get("/api/v1/guest/notices/campaign-check").status_code == 403
    denied_upload = _create_intent(client, notice, "legacy-read-only")
    assert denied_upload.status_code == 403
    assert denied_upload.json()["error"]["code"] == "GUEST_ACTION_NOT_ALLOWED"

    with client.app.state.database.session_factory() as session:
        membership = session.scalar(
            select(Membership).where(
                Membership.organization_id == ACME_ORG_ID,
                Membership.user_id == MARKETER_USER_ID,
            )
        )
        assert membership
        role = session.scalar(
            select(MembershipRole).where(
                MembershipRole.membership_id == membership.id,
                MembershipRole.role == "marketer",
            )
        )
        assert role
        session.delete(role)
        session.commit()
    assert client.get("/api/v1/guest/submission").status_code == 401


def test_guest_revision_appends_exact_next_version_and_rejects_stale_current(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, invitation, submission = issue_invitation(client, marketer_headers)
    assert submission is not None
    assert exchange(client, invitation_secret(invitation)).status_code == 200
    notice = _notice(client)
    intent_response = _create_intent(client, notice, "revision-source")
    assert intent_response.status_code == 201, intent_response.text
    intent = intent_response.json()
    assert _put(client, intent).status_code == 200
    assert _finalize(client, intent).status_code == 200
    context = client.get("/api/v1/guest/submission").json()
    current = context["submission"]["current_version"]
    assert current["version_no"] == 1
    response = client.post(
        "/api/v1/guest/submission-versions",
        headers=_origin_headers(**{"Idempotency-Key": "revision-version"}),
        json={
            "asset_id": intent["upload_id"],
            "caption": "Creator revision.",
            "expected_current_version_id": current["id"],
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["version_no"] == 2
    authoritative = client.get("/api/v1/guest/submission").json()
    assert authoritative["submission"]["current_version"] == {
        **response.json(),
        "consent_receipt_id": intent["consent_receipt"]["id"],
    }

    stale = client.post(
        "/api/v1/guest/submission-versions",
        headers=_origin_headers(**{"Idempotency-Key": "stale-revision"}),
        json={
            "asset_id": str(uuid4()),
            "caption": "Stale revision.",
            "expected_current_version_id": current["id"],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "SUBMISSION_VERSION_CONFLICT"


def test_guest_withdrawal_is_exact_source_scoped_idempotent_and_actor_attributed(
    client: TestClient,
    marketer_headers: dict[str, str],
) -> None:
    _campaign, invitation, _submission = issue_invitation(
        client, marketer_headers, empty_submission=True
    )
    assert exchange(client, invitation_secret(invitation)).status_code == 200
    notice = _notice(client)
    intent = _create_intent(client, notice, "withdraw-source").json()
    assert _put(client, intent).status_code == 200
    assert _finalize(client, intent).status_code == 200
    version = client.post(
        "/api/v1/guest/submission-versions",
        headers=_origin_headers(**{"Idempotency-Key": "withdraw-version"}),
        json={
            "asset_id": intent["upload_id"],
            "caption": "Withdraw this exact source.",
            "expected_current_version_id": None,
        },
    )
    assert version.status_code == 201, version.text
    scoped = client.get("/api/v1/guest/submission")
    assert scoped.status_code == 200
    assert scoped.json()["submission"]["current_version"]["consent_receipt_id"] == intent[
        "consent_receipt"
    ]["id"]

    url = f"/api/v1/guest/consent-receipts/{intent['consent_receipt']['id']}/withdraw"
    assert client.post(url).status_code == 403
    first = client.post(url, headers=_origin_headers())
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "completed"
    repeated = client.post(url, headers=_origin_headers())
    assert repeated.status_code == 202
    assert repeated.json()["id"] == first.json()["id"]

    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        receipt = session.get(ConsentReceipt, UUID(intent["consent_receipt"]["id"]))
        stored_version = session.get(SubmissionVersion, UUID(version.json()["id"]))
        deletion = session.get(DeletionRequest, UUID(first.json()["id"]))
        assert asset and asset.status == "deleted" and asset.object_bytes is None
        assert receipt and receipt.revocation_actor_kind == "guest"
        assert receipt.revocation_reason == "withdrawn" and receipt.revoked_by is None
        assert stored_version and stored_version.caption == ""
        assert deletion and deletion.requested_by_kind == "guest" and deletion.requested_by is None
        actions = session.scalars(
            select(AuditEvent.action).where(AuditEvent.actor_kind == "guest")
        ).all()
        assert "processing.authorization_revoked" in actions
        assert "deletion.completed" in actions
