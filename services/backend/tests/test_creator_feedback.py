from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from test_guard_regressions import completed_check
from test_guest_portal import exchange, invitation_secret
from test_workflow import upload_asset

from vouch_backend.models import CreatorFeedback


def _issue_invitation(
    client: TestClient,
    marketer_headers: dict[str, str],
    submission: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/campaigns/{submission['campaign_id']}/guest-invitations",
        headers=marketer_headers,
        json={
            "creator_id": submission["creator_id"],
            "submission_id": submission["id"],
            "recovery_id": str(uuid4()),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _draft(
    client: TestClient,
    marketer_headers: dict[str, str],
    check: dict[str, Any],
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/checks/{check['id']}/fix-request-drafts",
        headers=marketer_headers,
        json={"finding_ids": [check["findings"][0]["id"]]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_member_explicitly_publishes_allowlisted_feedback_for_creator(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
) -> None:
    submission, check = completed_check(client, marketer_headers, reviewer_headers)
    invitation = _issue_invitation(client, marketer_headers, submission)
    assert exchange(client, invitation_secret(invitation)).status_code == 200
    draft = _draft(client, marketer_headers, check)
    message = "Please make the sponsorship cue explicit in the first four seconds."
    body = {
        "fix_request_draft_id": draft["id"],
        "message": message,
        "start_ms": 0,
        "end_ms": 4000,
    }

    missing_key = client.post(
        f"/api/v1/checks/{check['id']}/creator-feedback",
        headers=marketer_headers,
        json=body,
    )
    assert missing_key.status_code == 400
    assert missing_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    published = client.post(
        f"/api/v1/checks/{check['id']}/creator-feedback",
        headers={**marketer_headers, "Idempotency-Key": "publish-feedback-v1"},
        json=body,
    )
    assert published.status_code == 201, published.text
    payload = published.json()
    assert payload == {
        "id": payload["id"],
        "submission_id": submission["id"],
        "submission_version_id": submission["versions"][0]["id"],
        "analysis_id": check["id"],
        "fix_request_draft_id": draft["id"],
        "version_no": 1,
        "message": message,
        "start_ms": 0,
        "end_ms": 4000,
        "invocation_mode": "fixture",
        "analysis_status": "completed",
        "manifest_hash": check["manifest_hash"],
        "published_at": payload["published_at"],
        "historical": False,
    }

    replay = client.post(
        f"/api/v1/checks/{check['id']}/creator-feedback",
        headers={**marketer_headers, "Idempotency-Key": "publish-feedback-v1"},
        json=body,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == payload
    conflict = client.post(
        f"/api/v1/checks/{check['id']}/creator-feedback",
        headers={**marketer_headers, "Idempotency-Key": "publish-feedback-v1"},
        json={**body, "message": "A different shared snapshot."},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    scoped = client.get("/api/v1/guest/submission")
    assert scoped.status_code == 200, scoped.text
    assert scoped.json()["feedback"] == [
        {
            "version_no": 1,
            "message": message,
            "start_ms": 0,
            "end_ms": 4000,
            "invocation_mode": "fixture",
            "analysis_status": "completed",
            "manifest_hash": check["manifest_hash"],
            "published_at": payload["published_at"],
            "historical": False,
        }
    ]

    revision_asset = upload_asset(client, marketer_headers, submission["campaign_id"])
    revision = client.post(
        f"/api/v1/submissions/{submission['id']}/versions",
        headers=marketer_headers,
        json={
            "asset_id": revision_asset["id"],
            "caption": "Clear sponsored fixture revision.",
            "rights_attested": True,
        },
    )
    assert revision.status_code == 201, revision.text
    historical = client.get("/api/v1/guest/submission")
    assert historical.status_code == 200, historical.text
    assert historical.json()["feedback"][0]["historical"] is True


def test_feedback_publication_validates_scope_range_and_active_version(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
) -> None:
    submission, check = completed_check(client, marketer_headers, reviewer_headers)
    draft = _draft(client, marketer_headers, check)
    url = f"/api/v1/checks/{check['id']}/creator-feedback"
    headers = {**marketer_headers, "Idempotency-Key": "feedback-range"}

    unpaired = client.post(
        url,
        headers=headers,
        json={
            "fix_request_draft_id": draft["id"],
            "message": "Selected creator feedback.",
            "start_ms": 0,
        },
    )
    assert unpaired.status_code == 422
    reversed_range = client.post(
        url,
        headers=headers,
        json={
            "fix_request_draft_id": draft["id"],
            "message": "Selected creator feedback.",
            "start_ms": 4000,
            "end_ms": 1000,
        },
    )
    assert reversed_range.status_code == 422
    outside_source = client.post(
        url,
        headers=headers,
        json={
            "fix_request_draft_id": draft["id"],
            "message": "Selected creator feedback.",
            "start_ms": 0,
            "end_ms": 11_000,
        },
    )
    assert outside_source.status_code == 422
    assert outside_source.json()["error"]["code"] == "FEEDBACK_RANGE_INVALID"

    revision_asset = upload_asset(client, marketer_headers, submission["campaign_id"])
    revision = client.post(
        f"/api/v1/submissions/{submission['id']}/versions",
        headers=marketer_headers,
        json={
            "asset_id": revision_asset["id"],
            "caption": "A newer immutable revision.",
            "rights_attested": True,
        },
    )
    assert revision.status_code == 201, revision.text
    stale = client.post(
        url,
        headers={**marketer_headers, "Idempotency-Key": "feedback-stale"},
        json={
            "fix_request_draft_id": draft["id"],
            "message": "This old instruction must not be newly published.",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "FEEDBACK_CONTEXT_CHANGED"


def test_submission_deletion_scrubs_published_feedback_snapshot(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
) -> None:
    submission, check = completed_check(client, marketer_headers, reviewer_headers)
    draft = _draft(client, marketer_headers, check)
    published = client.post(
        f"/api/v1/checks/{check['id']}/creator-feedback",
        headers={**marketer_headers, "Idempotency-Key": "feedback-to-scrub"},
        json={
            "fix_request_draft_id": draft["id"],
            "message": "This shared snapshot must be erased with its source.",
        },
    )
    assert published.status_code == 201, published.text

    deletion = client.post(
        "/api/v1/deletion-requests",
        headers=marketer_headers,
        json={"resource_type": "submission", "resource_id": submission["id"]},
    )
    assert deletion.status_code == 202, deletion.text
    with client.app.state.database.session_factory() as session:
        feedback = session.scalar(select(CreatorFeedback))
        assert feedback is not None
        assert feedback.message == ""
        assert feedback.start_ms is None
        assert feedback.end_ms is None
