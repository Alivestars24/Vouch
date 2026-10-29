from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_workflow import MP4, create_campaign, create_submission, start_check

from vouch_backend.models import (
    Approval,
    Campaign,
    EvidenceItem,
    Finding,
    FindingDecision,
    FixRequestDraft,
    MediaAsset,
    Organization,
    ReviewContext,
    ReviewEvent,
    RulePackVersion,
    SubmissionVersion,
    utcnow,
)
from vouch_backend.providers import FixtureProviders
from vouch_backend.worker import (
    _job_inputs,
    _publish_success,
    claim_next_job,
    process_next_job,
)


@pytest.mark.parametrize("stage", ["before_check", "before_publication"])
def test_expired_source_blocks_work_caption_delivery_and_publication(
    client: TestClient, marketer_headers: dict[str, str], stage: str
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version = submission["versions"][0]
    database = client.app.state.database
    if stage == "before_publication":
        command = start_check(client, marketer_headers, version["id"], "clean", "expiry-guard")
        assert command.status_code == 202
        claim = claim_next_job(database, "expiry-guard-worker")
        assert claim is not None
        context, _ = _job_inputs(database, claim)
        providers = FixtureProviders()
        evidence = [providers.transcriber.transcribe(context), providers.segmenter.segment(context)]
        findings = providers.reasoner.evaluate(context, evidence)
    with database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(version["asset_id"]))
        assert asset is not None
        asset.retention_deadline = utcnow() - timedelta(seconds=1)
        session.commit()
    expired = start_check(client, marketer_headers, version["id"], "clean", "after-expiry")
    assert expired.status_code == 409 and expired.json()["error"]["code"] == "RESOURCE_EXPIRED"
    history = client.get(f"/api/v1/submissions/{submission['id']}", headers=marketer_headers).json()
    assert history["versions"][0]["caption"] == ""
    assert not history["versions"][0]["source_available"]
    if stage == "before_publication":
        assert not _publish_success(database, claim, evidence, findings)
        job = client.get(command.json()["status_url"], headers=marketer_headers).json()
        assert job["status"] == "cancelled"
        with database.session_factory() as session:
            assert not session.scalars(select(EvidenceItem)).all()


def completed_check(
    client: TestClient, marketer: dict[str, str], reviewer: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    campaign = create_campaign(client, marketer)
    submission = create_submission(client, marketer, campaign)
    command = start_check(
        client, marketer, submission["versions"][0]["id"], "success", "guard-check"
    )
    assert command.status_code == 202, command.text
    assert process_next_job(client.app.state.database)
    response = client.get(f"/api/v1/checks/{command.json()['resource_id']}", headers=reviewer)
    assert response.status_code == 200, response.text
    return submission, response.json()


def decide(
    client: TestClient,
    reviewer: dict[str, str],
    check: dict[str, Any],
    decision: str,
    revision: int,
) -> Any:
    return client.post(
        f"/api/v1/findings/{check['findings'][0]['id']}/decisions",
        headers=reviewer,
        json={
            "decision": decision,
            "rationale": "A deliberate reviewer finding decision.",
            "expected_review_version": revision,
        },
    )


def approve(
    client: TestClient, reviewer: dict[str, str], check: dict[str, Any], revision: int
) -> Any:
    return client.post(
        f"/api/v1/checks/{check['id']}/review-decisions",
        headers=reviewer,
        json={
            "action": "approve",
            "expected_review_version": revision,
            "manifest_hash": check["manifest_hash"],
            "rationale": "Human review of this exact evidence and finding revision.",
        },
    )


def test_changed_finding_decisions_reopen_approval_without_inheritance(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
) -> None:
    _, check = completed_check(client, marketer_headers, reviewer_headers)
    assert decide(client, reviewer_headers, check, "dismissed", 1).status_code == 200
    assert approve(client, reviewer_headers, check, 2).status_code == 200
    assert approve(client, reviewer_headers, check, 3).status_code == 409
    approved = client.get(f"/api/v1/checks/{check['id']}", headers=reviewer_headers).json()
    assert approved["approval"] is not None

    changed = decide(client, reviewer_headers, check, "accepted", 3)
    assert changed.status_code == 200, changed.text
    assert changed.json()["review_status"] == "unreviewed"
    reopened = client.get(f"/api/v1/checks/{check['id']}", headers=reviewer_headers).json()
    assert reopened["approval"] is None
    assert reopened["findings"][0]["decision"]["decision"] == "accepted"
    assert approve(client, reviewer_headers, check, 3).status_code == 409
    assert approve(client, reviewer_headers, check, 4).status_code == 422

    assert decide(client, reviewer_headers, check, "incorrect", 4).status_code == 200
    assert approve(client, reviewer_headers, check, 5).status_code == 200
    with client.app.state.database.session_factory() as session:
        approvals = session.scalars(
            select(Approval)
            .where(Approval.analysis_id == UUID(check["id"]))
            .order_by(Approval.review_revision)
        ).all()
        assert [row.review_revision for row in approvals] == [3, 6]
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReviewEvent)
                .where(ReviewEvent.action == "finding_decisions_changed")
            )
            == 1
        )


def test_submission_deletion_redacts_derivatives_and_freezes_review(
    client: TestClient,
    marketer_headers: dict[str, str],
    reviewer_headers: dict[str, str],
) -> None:
    submission, check = completed_check(client, marketer_headers, reviewer_headers)
    assert decide(client, reviewer_headers, check, "dismissed", 1).status_code == 200
    assert approve(client, reviewer_headers, check, 2).status_code == 200
    draft = client.post(
        f"/api/v1/checks/{check['id']}/fix-request-drafts",
        headers=marketer_headers,
        json={"finding_ids": [check["findings"][0]["id"]]},
    )
    assert draft.status_code == 201, draft.text
    deletion = client.post(
        "/api/v1/deletion-requests",
        headers=marketer_headers,
        json={"resource_type": "submission", "resource_id": submission["id"]},
    )
    assert deletion.status_code == 202, deletion.text
    repeated = client.post(
        "/api/v1/deletion-requests",
        headers=marketer_headers,
        json={"resource_type": "submission", "resource_id": submission["id"]},
    )
    assert repeated.json()["id"] == deletion.json()["id"]
    assert decide(client, reviewer_headers, check, "accepted", 4).status_code == 409
    assert approve(client, reviewer_headers, check, 4).status_code == 409
    assert client.get(f"/api/v1/checks/{check['id']}", headers=reviewer_headers).status_code == 409

    with client.app.state.database.session_factory() as session:
        version = session.get(SubmissionVersion, UUID(submission["versions"][0]["id"]))
        assert version is not None and version.caption == ""
        asset = session.get(MediaAsset, version.asset_id)
        assert asset is not None and asset.object_bytes is None and asset.filename == ""
        context = session.scalar(
            select(ReviewContext).where(ReviewContext.analysis_id == UUID(check["id"]))
        )
        assert context is not None and context.review_status == "revoked"
        assert all(row.description == "" for row in session.scalars(select(EvidenceItem)))
        assert all(
            row.evidence_text == row.uncertainty == row.suggested_action == ""
            for row in session.scalars(select(Finding))
        )
        assert all(row.rationale == "" for row in session.scalars(select(FindingDecision)))
        assert all(row.rationale == "" for row in session.scalars(select(ReviewEvent)))
        assert all(row.text == "" for row in session.scalars(select(FixRequestDraft)))
        assert session.scalar(select(func.count()).select_from(Approval)) == 1


def test_asset_deletion_fences_inflight_publication_and_releases_fixture_reservation(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version = submission["versions"][0]
    command = start_check(client, marketer_headers, version["id"], "success", "asset-race")
    database = client.app.state.database
    claim = claim_next_job(database, "inflight-provider")
    assert claim is not None
    context, _ = _job_inputs(database, claim)
    providers = FixtureProviders()
    evidence = [
        providers.transcriber.transcribe(context),
        providers.segmenter.segment(context),
    ]
    findings = providers.reasoner.evaluate(context, evidence)
    deletion = client.post(
        "/api/v1/deletion-requests",
        headers=marketer_headers,
        json={"resource_type": "media_asset", "resource_id": version["asset_id"]},
    )
    assert deletion.status_code == 202, deletion.text
    assert not _publish_success(database, claim, evidence, findings)
    job = client.get(command.json()["status_url"], headers=marketer_headers).json()
    assert job["status"] == "cancelled"
    assert not process_next_job(database)
    retry = start_check(client, marketer_headers, version["id"], "clean", "asset-deleted")
    assert retry.status_code in {409, 422}
    with database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(EvidenceItem)) == 0
        assert session.scalar(select(func.count()).select_from(Finding)) == 0
        organization = session.get(Organization, UUID(marketer_headers["X-Organization-Id"]))
        assert organization is not None and organization.budget_held_minor == 0


def test_worker_uses_exact_campaign_rule_pin(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    with client.app.state.database.session_factory() as session:
        session.add(
            RulePackVersion(
                id=UUID("00000000-0000-4000-8000-000000000001"),
                organization_id=UUID(marketer_headers["X-Organization-Id"]),
                name="Unrelated draft policy",
                version="99.0",
                status="draft",
                source_uri="fixture://unrelated",
                content_hash="0" * 64,
                rules=[{"id": "UNRELATED_RULE", "version": "99.0"}],
            )
        )
        session.commit()
    command = start_check(
        client, marketer_headers, submission["versions"][0]["id"], "success", "exact-pin"
    )
    assert process_next_job(client.app.state.database)
    job = client.get(command.json()["status_url"], headers=marketer_headers).json()
    assert job["status"] == "succeeded"


def test_worker_rejects_a_changed_input_snapshot(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    command = start_check(
        client, marketer_headers, submission["versions"][0]["id"], "success", "changed-pin"
    )
    with client.app.state.database.session_factory() as session:
        persisted_campaign = session.get(Campaign, UUID(campaign["id"]))
        assert persisted_campaign is not None
        pack = session.get(RulePackVersion, persisted_campaign.rule_pack_version_id)
        assert pack is not None
        pack.content_hash = "f" * 64
        session.commit()
    assert process_next_job(client.app.state.database)
    job = client.get(command.json()["status_url"], headers=marketer_headers).json()
    assert job["status"] == "failed"
    assert job["last_error"]["code"] == "INPUT_SNAPSHOT_CHANGED"


@pytest.mark.parametrize("at_finalize", [False, True])
def test_upload_capability_expiry_is_enforced(
    client: TestClient, marketer_headers: dict[str, str], at_finalize: bool
) -> None:
    from test_workflow import NOTICE_ACKNOWLEDGMENT

    campaign = create_campaign(client, marketer_headers)
    response = client.post(
        "/api/v1/uploads",
        headers=marketer_headers,
        json={
            "campaign_id": campaign["id"],
            "filename": "expired-fixture.mp4",
            **NOTICE_ACKNOWLEDGMENT,
            "content_type": "video/mp4",
            "byte_size": len(MP4),
            "rights_attested": True,
        },
    )
    assert response.status_code == 201, response.text
    intent = response.json()
    content_headers = {"X-Upload-Token": intent["upload_token"], "Content-Type": "video/mp4"}
    if at_finalize:
        uploaded = client.put(intent["content_url"], headers=content_headers, content=MP4)
        assert uploaded.status_code == 200
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert asset is not None
        asset.created_at -= timedelta(minutes=6)
        session.commit()
    if at_finalize:
        expired = client.post(
            f"/api/v1/uploads/{intent['upload_id']}/finalize",
            headers=marketer_headers,
            json={"finalize_token": intent["finalize_token"]},
        )
    else:
        expired = client.put(intent["content_url"], headers=content_headers, content=MP4)
    assert expired.status_code == 401, expired.text
    assert expired.json()["error"]["code"] == "UPLOAD_AUTHORIZATION_EXPIRED"
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        assert asset is not None and asset.validated_content_type is None
        if not at_finalize:
            assert asset.object_bytes is None
