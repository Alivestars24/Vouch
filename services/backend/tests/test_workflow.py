from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from vouch_backend.models import Organization
from vouch_backend.notices import CURRENT_NOTICE_VERSION
from vouch_backend.worker import process_next_job, run_until_idle

MP4 = bytes(
    [
        0x00,
        0x00,
        0x00,
        0x18,
        0x66,
        0x74,
        0x79,
        0x70,
        0x69,
        0x73,
        0x6F,
        0x6D,
        0x00,
        0x00,
        0x02,
        0x00,
        0x69,
        0x73,
        0x6F,
        0x6D,
        0x69,
        0x73,
        0x6F,
        0x32,
    ]
)
NOTICE_ACKNOWLEDGMENT = {
    "notice_version": CURRENT_NOTICE_VERSION,
    "notice_acknowledged": True,
    "purpose": "campaign_check",
}


def first_item(client: TestClient, path: str, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get(path, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"][0]


def create_campaign(client: TestClient, headers: dict[str, str]) -> dict[str, Any]:
    product = first_item(client, "/api/v1/products", headers)
    creator = first_item(client, "/api/v1/creators", headers)
    pack = first_item(client, "/api/v1/rule-pack-versions", headers)
    response = client.post(
        "/api/v1/campaigns",
        headers=headers,
        json={
            "name": "Synthetic launch",
            "objective": "Review an authorized creator draft",
            "market": "IN",
            "product_id": product["id"],
            "rule_pack_version_id": pack["id"],
            "creator_ids": [creator["id"]],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload_asset(client: TestClient, headers: dict[str, str], campaign_id: str) -> dict[str, Any]:
    intent = client.post(
        "/api/v1/uploads",
        headers=headers,
        json={
            "campaign_id": campaign_id,
            "filename": "authorized-synthetic.mp4",
            **NOTICE_ACKNOWLEDGMENT,
            "content_type": "video/mp4",
            "byte_size": len(MP4),
            "rights_attested": True,
        },
    )
    assert intent.status_code == 201, intent.text
    authorization = intent.json()
    put = client.put(
        authorization["content_url"],
        headers={
            **headers,
            "Content-Type": "video/mp4",
            "X-Upload-Token": authorization["upload_token"],
        },
        content=MP4,
    )
    assert put.status_code == 200, put.text
    finalized = client.post(
        f"/api/v1/uploads/{authorization['upload_id']}/finalize",
        headers=headers,
        json={"finalize_token": authorization["finalize_token"]},
    )
    assert finalized.status_code == 200, finalized.text
    return finalized.json()


def create_submission(
    client: TestClient, headers: dict[str, str], campaign: dict[str, Any]
) -> dict[str, Any]:
    asset = upload_asset(client, headers, campaign["id"])
    response = client.post(
        f"/api/v1/campaigns/{campaign['id']}/submissions",
        headers=headers,
        json={
            "asset_id": asset["id"],
            "creator_id": campaign["creator_ids"][0],
            "caption": "New frames. Sponsored fixture draft.",
            "rights_attested": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def start_check(
    client: TestClient,
    headers: dict[str, str],
    version_id: str,
    scenario: str,
    key: str,
) -> Any:
    return client.post(
        f"/api/v1/submission-versions/{version_id}/checks",
        headers={**headers, "Idempotency-Key": key},
        json={
            "scenario": scenario,
            "invocation_mode": "fixture",
            "schema_version": "check-result.v1",
        },
    )


def test_complete_revision_and_exact_version_approval(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
    beta_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version_one = submission["versions"][0]
    accepted = start_check(client, marketer_headers, version_one["id"], "success", "check-v1")
    assert accepted.status_code == 202
    assert process_next_job(client.app.state.database)
    job = client.get(accepted.json()["status_url"], headers=marketer_headers).json()
    assert job["status"] == "succeeded"

    check_id = accepted.json()["resource_id"]
    check = client.get(f"/api/v1/checks/{check_id}", headers=reviewer_headers).json()
    assert check["analysis_status"] == "completed"
    assert check["machine_assessment"] == "fixes_suggested"
    assert check["review_status"] == "unreviewed"
    assert check["findings"][0]["time_range"] == {"start_ms": 0, "end_ms": 4000}
    unavailable_report = client.get(
        f"/api/v1/checks/{check_id}/approval-report", headers=reviewer_headers
    )
    assert unavailable_report.status_code == 409
    assert unavailable_report.json()["error"]["code"] == "APPROVAL_REPORT_UNAVAILABLE"

    blocked = client.post(
        f"/api/v1/checks/{check_id}/review-decisions",
        headers=reviewer_headers,
        json={
            "action": "approve",
            "expected_review_version": 1,
            "manifest_hash": check["manifest_hash"],
            "rationale": "Review complete.",
        },
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "REQUIRED_REVIEW_INCOMPLETE"

    finding_id = check["findings"][0]["id"]
    decision = client.post(
        f"/api/v1/findings/{finding_id}/decisions",
        headers=reviewer_headers,
        json={
            "decision": "dismissed",
            "rationale": "The explicit caption and spoken cue satisfy this draft brand policy.",
            "expected_review_version": 1,
        },
    )
    assert decision.status_code == 200
    approval = client.post(
        f"/api/v1/checks/{check_id}/review-decisions",
        headers=reviewer_headers,
        json={
            "action": "approve",
            "expected_review_version": 2,
            "manifest_hash": check["manifest_hash"],
            "rationale": "Human review completed for version one.",
        },
    )
    assert approval.status_code == 200
    assert approval.json()["review_status"] == "approved"
    report_response = client.get(
        f"/api/v1/checks/{check_id}/approval-report", headers=reviewer_headers
    )
    assert report_response.status_code == 200, report_response.text
    assert report_response.headers["cache-control"] == "no-store"
    report = report_response.json()
    assert report["report_version"] == "approval-report.v1"
    assert report["current_status"] == "approved"
    assert report["submission_version_id"] == version_one["id"]
    assert report["submission_version_no"] == 1
    assert report["manifest_hash"] == check["manifest_hash"]
    assert report["media_hash"] == version_one["media_hash"]
    assert report["caption_hash"] == version_one["caption_hash"]
    assert report["approval_rationale"] == "Human review completed for version one."
    assert report["findings"][0]["decision"] == "dismissed"
    assert report["limitations"]
    foreign_report = client.get(
        f"/api/v1/checks/{check_id}/approval-report", headers=beta_headers
    )
    assert foreign_report.status_code == 404

    revision_asset = upload_asset(client, marketer_headers, campaign["id"])
    revision = client.post(
        f"/api/v1/submissions/{submission['id']}/versions",
        headers=marketer_headers,
        json={
            "asset_id": revision_asset["id"],
            "caption": "Clear sponsored fixture revision.",
            "rights_attested": True,
        },
    )
    assert revision.status_code == 201
    version_two = revision.json()["versions"][-1]
    assert version_two["version_no"] == 2
    historical = client.get(f"/api/v1/checks/{check_id}", headers=reviewer_headers).json()
    assert historical["review_status"] == "superseded"
    superseded_report = client.get(
        f"/api/v1/checks/{check_id}/approval-report", headers=reviewer_headers
    )
    assert superseded_report.status_code == 409

    clean = start_check(client, marketer_headers, version_two["id"], "clean", "check-v2")
    assert clean.status_code == 202
    assert process_next_job(client.app.state.database)
    clean_check = client.get(
        f"/api/v1/checks/{clean.json()['resource_id']}", headers=reviewer_headers
    ).json()
    assert clean_check["machine_assessment"] == "no_issues_detected"
    approved_two = client.post(
        f"/api/v1/checks/{clean_check['id']}/review-decisions",
        headers=reviewer_headers,
        json={
            "action": "approve",
            "expected_review_version": 1,
            "manifest_hash": clean_check["manifest_hash"],
            "rationale": "Human review completed for version two.",
        },
    )
    assert approved_two.status_code == 200
    assert approved_two.json()["submission_version_id"] == version_two["id"]
    current_report = client.get(
        f"/api/v1/checks/{clean_check['id']}/approval-report", headers=reviewer_headers
    )
    assert current_report.status_code == 200, current_report.text
    assert current_report.json()["submission_version_no"] == 2
    assert current_report.json()["findings"] == []

    revoked = client.post(
        f"/api/v1/checks/{clean_check['id']}/review-decisions",
        headers=reviewer_headers,
        json={
            "action": "revoke",
            "expected_review_version": 2,
            "manifest_hash": clean_check["manifest_hash"],
            "rationale": "Approval withdrawn after a later human review.",
        },
    )
    assert revoked.status_code == 200
    assert revoked.json()["review_status"] == "revoked"
    revoked_report = client.get(
        f"/api/v1/checks/{clean_check['id']}/approval-report", headers=reviewer_headers
    )
    assert revoked_report.status_code == 409


def test_partial_evidence_roles_and_tenant_scope(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
    admin_headers: dict[str, str],
    beta_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version = submission["versions"][0]
    accepted = start_check(client, marketer_headers, version["id"], "partial_voice", "partial")
    assert process_next_job(client.app.state.database)
    check = client.get(
        f"/api/v1/checks/{accepted.json()['resource_id']}", headers=reviewer_headers
    ).json()
    assert check["analysis_status"] == "partial"
    assert check["machine_assessment"] == "human_review_required"
    assert check["missing_intervals"][0]["modality"] == "speech"

    denied = client.post(
        f"/api/v1/findings/{check['findings'][0]['id']}/decisions",
        headers=marketer_headers,
        json={
            "decision": "accepted",
            "rationale": "Attempted marketer decision.",
            "expected_review_version": 1,
        },
    )
    assert denied.status_code == 403
    admin_approval = client.post(
        f"/api/v1/checks/{check['id']}/review-decisions",
        headers=admin_headers,
        json={
            "action": "approve",
            "expected_review_version": 1,
            "manifest_hash": check["manifest_hash"],
            "rationale": "Admin is not implicitly a reviewer.",
        },
    )
    assert admin_approval.status_code == 403
    cross_tenant = client.get(f"/api/v1/campaigns/{campaign['id']}", headers=beta_headers)
    assert cross_tenant.status_code == 404


def test_idempotency_retry_exhaustion_and_budget(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version_id = submission["versions"][0]["id"]
    first = start_check(client, marketer_headers, version_id, "transient_then_success", "same")
    duplicate = start_check(client, marketer_headers, version_id, "transient_then_success", "same")
    assert first.status_code == 202
    assert duplicate.status_code == 200
    assert duplicate.json()["operation_id"] == first.json()["operation_id"]
    conflict = start_check(client, marketer_headers, version_id, "clean", "same")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    assert process_next_job(client.app.state.database)
    retrying = client.get(first.json()["status_url"], headers=marketer_headers).json()
    assert retrying["status"] == "retry_wait"
    time.sleep(0.2)
    assert process_next_job(client.app.state.database)
    succeeded = client.get(first.json()["status_url"], headers=marketer_headers).json()
    assert succeeded["status"] == "succeeded"
    assert succeeded["attempt_count"] == 2

    failing = start_check(client, marketer_headers, version_id, "provider_down", "down")
    assert failing.status_code == 202
    assert run_until_idle(client.app.state.database, max_cycles=5) == 3
    failed_job = client.get(failing.json()["status_url"], headers=marketer_headers).json()
    assert failed_job["status"] == "dead_letter"
    assert failed_job["attempt_count"] == 3

    with client.app.state.database.session_factory() as session:
        org = session.get(Organization, UUID("11111111-1111-4111-8111-111111111111"))
        assert org is not None
        org.budget_cap_minor = 20
        session.commit()
    budget_denied = start_check(client, marketer_headers, version_id, "success", "budget")
    assert budget_denied.status_code == 429
    assert budget_denied.json()["error"]["code"] == "BUDGET_EXCEEDED"


def test_deletion_cancels_queued_work_and_blocks_publish(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    accepted = start_check(
        client,
        marketer_headers,
        submission["versions"][0]["id"],
        "success",
        "delete-race",
    )
    deletion = client.post(
        "/api/v1/deletion-requests",
        headers=marketer_headers,
        json={"resource_type": "submission", "resource_id": submission["id"]},
    )
    assert deletion.status_code == 202
    assert deletion.json()["status"] == "completed"
    job = client.get(accepted.json()["status_url"], headers=marketer_headers).json()
    assert job["status"] == "cancelled"
    assert not process_next_job(client.app.state.database)
    retry = start_check(
        client,
        marketer_headers,
        submission["versions"][0]["id"],
        "success",
        "after-delete",
    )
    assert retry.status_code in {404, 409}
