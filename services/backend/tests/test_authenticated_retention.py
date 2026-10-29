"""Opt-in local Storage erasure under an isolated, non-bypass retention login."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from test_authenticated_integration import LocalRuntime, env_file
from test_authenticated_integration import runtime as runtime
from test_workflow import create_campaign, create_submission, start_check, upload_asset

from vouch_backend.config import Settings
from vouch_backend.db import Database, set_database_scope
from vouch_backend.models import (
    Analysis,
    Approval,
    AuditEvent,
    BudgetReservation,
    ConsentReceipt,
    DeletionRequest,
    EvidenceItem,
    Finding,
    FindingDecision,
    FixRequestDraft,
    Job,
    MediaAsset,
    Organization,
    ReviewContext,
    ReviewEvent,
    SubmissionVersion,
    Tombstone,
    utcnow,
)
from vouch_backend.retention import reconcile_once
from vouch_backend.seed import ACME_ORG_ID, BETA_ORG_ID
from vouch_backend.storage import SupabaseMediaStore
from vouch_backend.worker import process_next_job

pytestmark = pytest.mark.skipif(
    os.getenv("VOUCH_TEST_AUTHENTICATED") != "1", reason="Opt-in local Supabase integration."
)


@pytest.fixture(scope="module")
def retention_runtime(runtime: dict[str, Any]) -> Iterator[dict[str, Any]]:  # noqa: F811
    environment = env_file("retention")
    url = make_url(environment["VOUCH_DATABASE_URL"])
    assert url.host == "127.0.0.1" and url.port == 54322
    assert url.username == "vouch_local_retention"
    assert environment["VOUCH_SUPABASE_URL"] == "http://127.0.0.1:54321"
    settings = Settings(
        database_url=environment["VOUCH_DATABASE_URL"],
        environment="test",
        auth_mode="supabase",
        supabase_url=environment["VOUCH_SUPABASE_URL"],
        supabase_publishable_key=environment["VOUCH_SUPABASE_PUBLISHABLE_KEY"],
        supabase_secret_key=environment["VOUCH_SUPABASE_SECRET_KEY"],
    )
    database = Database(settings.database_url, runtime_role="vouch_retention")
    try:
        yield LocalRuntime(
            {
                **runtime,
                "retention": database,
                "retention_settings": settings,
                "store": SupabaseMediaStore(settings),
            }
        )
    finally:
        database.dispose()


def _complete_and_review(current: dict[str, Any], analysis_id: UUID) -> None:
    client = current["client"]
    reviewer = current["headers"]["reviewer"]
    check_url = f"/api/v1/checks/{analysis_id}"
    for _ in range(30):
        check = client.get(check_url, headers=reviewer).json()
        if check["analysis_status"] == "completed":
            break
        assert process_next_job(current["worker"])
    else:
        pytest.fail("Local Check did not finish within the bounded integration run.")
    finding = check["findings"][0]
    draft = client.post(
        f"{check_url}/fix-request-drafts",
        headers=current["headers"]["marketer"],
        json={"finding_ids": [finding["id"]]},
    )
    assert draft.status_code == 201, draft.text
    decision = client.post(
        f"/api/v1/findings/{finding['id']}/decisions",
        headers=reviewer,
        json={
            "decision": "dismissed",
            "rationale": "Synthetic private decision rationale for expiration proof.",
            "expected_review_version": 1,
        },
    )
    assert decision.status_code == 200, decision.text
    approved = client.post(
        f"{check_url}/review-decisions",
        headers=reviewer,
        json={
            "action": "approve",
            "expected_review_version": 2,
            "manifest_hash": check["manifest_hash"],
            "rationale": "Synthetic exact-version human approval before expiry.",
        },
    )
    assert approved.status_code == 200 and approved.json()["review_status"] == "approved"


def _assert_private_storage_absent(settings: Settings, key: str) -> None:
    assert settings.supabase_secret_key
    headers = {"apikey": settings.supabase_secret_key}
    if settings.supabase_secret_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {settings.supabase_secret_key}"
    response = httpx.get(
        f"{settings.supabase_url}/storage/v1/object/authenticated/vouch-media/{key}",
        headers=headers,
        timeout=10,
        follow_redirects=False,
    )
    assert response.status_code == 404 or str(response.json().get("statusCode")) == "404"


@pytest.mark.parametrize("completed_check", [True, False], ids=["reviewed", "queued"])
def test_restricted_retention_erases_real_private_source_and_derivatives(
    retention_runtime: dict[str, Any], completed_check: bool
) -> None:
    current = retention_runtime
    client, owner = current["client"], current["owner"]
    marketer = current["headers"]["marketer"]
    campaign = create_campaign(client, marketer)
    submission = create_submission(client, marketer, campaign)
    version = submission["versions"][0]
    asset_id = UUID(version["asset_id"])
    accepted = start_check(client, marketer, version["id"], "success", uuid4().hex)
    assert accepted.status_code == 202, accepted.text
    analysis_id = UUID(accepted.json()["resource_id"])
    if completed_check:
        _complete_and_review(current, analysis_id)

    deadline = utcnow() - timedelta(minutes=1)
    with owner.session_factory() as session:
        asset = session.get(MediaAsset, asset_id)
        assert asset and asset.object_key and asset.storage_backend == "supabase"
        object_key = asset.object_key
        asset.retention_deadline = deadline  # Owner advances only this synthetic source deadline.
        session.commit()
        analysis = session.get(Analysis, analysis_id)
        assert analysis and analysis.job_id
        job_id = analysis.job_id
        job = session.get(Job, job_id)
        assert job
        original_fence = job.fence
        approvals_before = len(
            session.scalars(select(Approval).where(Approval.analysis_id == analysis_id)).all()
        )
        assert approvals_before == int(completed_check)
        organization = session.get(Organization, ACME_ORG_ID)
        assert organization
        held_before = organization.budget_held_minor

    assert client.get(
        f"/api/v1/uploads/{asset_id}/content", headers=marketer
    ).status_code == 404
    receipt_id = None
    for _ in range(50):
        assert reconcile_once(
            current["retention"], current["store"], worker_id="restricted-retention-integration"
        )
        with owner.session_factory() as session:
            receipt = session.scalar(
                select(DeletionRequest).where(
                    DeletionRequest.organization_id == ACME_ORG_ID,
                    DeletionRequest.resource_type == "media_asset",
                    DeletionRequest.resource_id == asset_id,
                )
            )
            if receipt is not None:
                assert receipt.status == "completed"
                assert receipt.requested_by is None and receipt.requested_by_kind == "retention"
                assert receipt.attempt_count == 1 and receipt.fence == 1
                assert receipt.completed_at is not None and receipt.lease_owner is None
                storage_destination = next(
                    item for item in receipt.destinations
                    if item["destination"] == "supabase_storage"
                )
                assert storage_destination["status"] == "completed"
                receipt_id = receipt.id
                break
    assert receipt_id is not None

    with owner.session_factory() as session:
        asset = session.get(MediaAsset, asset_id)
        assert asset and asset.status == "deleted" and asset.deleted_at is not None
        assert asset.retention_deadline == deadline
        assert asset.filename == "" and asset.object_bytes is None
        authorization = session.scalar(
            select(ConsentReceipt).where(ConsentReceipt.asset_id == asset_id)
        )
        assert authorization and authorization.revoked_at
        assert authorization.revoked_by is None
        assert authorization.revocation_actor_kind == "retention"
        assert authorization.revocation_reason == "expired"
        authorization_event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.resource_id == authorization.id,
                AuditEvent.action == "processing.authorization_revoked",
            )
        )
        assert authorization_event and authorization_event.actor_kind == "retention"
        assert authorization_event.actor_user_id is None
        stored_version = session.get(SubmissionVersion, UUID(version["id"]))
        assert stored_version and stored_version.caption == ""
        analysis = session.get(Analysis, analysis_id)
        assert analysis and analysis.machine_assessment == "not_assessed"
        assert analysis.observed_coverage == [] and analysis.missing_intervals == []
        context = session.scalar(
            select(ReviewContext).where(ReviewContext.analysis_id == analysis_id)
        )
        if completed_check:
            assert context and context.review_status == "revoked"
        else:
            assert context is None  # A queued Check has not created a review context.
        assert session.scalar(
            select(Tombstone).where(Tombstone.resource_id == asset_id)
        ) is not None
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.resource_id == receipt_id)
        ).all()
        assert {event.action for event in events} >= {
            "deletion.requested", "deletion.attempt_started", "deletion.completed"
        }
        assert all(
            event.actor_kind == "retention" and event.actor_user_id is None for event in events
        )
        job = session.get(Job, job_id)
        assert job
        if completed_check:
            assert context
            evidence = session.scalars(
                select(EvidenceItem).where(EvidenceItem.analysis_id == analysis_id)
            ).all()
            findings = session.scalars(
                select(Finding).where(Finding.analysis_id == analysis_id)
            ).all()
            decisions = session.scalars(
                select(FindingDecision).where(FindingDecision.review_context_id == context.id)
            ).all()
            review_events = session.scalars(
                select(ReviewEvent).where(ReviewEvent.review_context_id == context.id)
            ).all()
            drafts = session.scalars(
                select(FixRequestDraft).where(FixRequestDraft.analysis_id == analysis_id)
            ).all()
            assert evidence and all(item.description == "" for item in evidence)
            assert findings and all(
                item.evidence_text == item.uncertainty == item.suggested_action == ""
                for item in findings
            )
            assert decisions and all(item.rationale == "" for item in decisions)
            assert review_events and all(item.rationale == "" for item in review_events)
            assert drafts and all(item.text == "" for item in drafts)
            assert len(
                session.scalars(select(Approval).where(Approval.analysis_id == analysis_id)).all()
            ) == approvals_before
        else:
            assert job.status == "cancelled" and job.fence == original_fence + 1
            assert job.lease_owner is None and job.lease_until is None
            assert analysis.analysis_status == "cancelled"
            reservation = session.scalar(
                select(BudgetReservation).where(BudgetReservation.job_id == job_id)
            )
            assert reservation and reservation.status == "released"
            organization = session.get(Organization, ACME_ORG_ID)
            assert organization and organization.budget_held_minor == held_before - 25
    _assert_private_storage_absent(current["retention_settings"], object_key)
    receipt = client.get(f"/api/v1/deletion-requests/{receipt_id}", headers=marketer)
    assert receipt.status_code == 200 and receipt.json()["status"] == "completed"


def test_retention_role_reopened_pool_is_narrow_and_cannot_impersonate_review(
    retention_runtime: dict[str, Any]
) -> None:
    current = retention_runtime
    client, owner = current["client"], current["owner"]
    campaign = create_campaign(client, current["headers"]["marketer"])
    active_asset = upload_asset(client, current["headers"]["marketer"], campaign["id"])
    foreign_campaign = create_campaign(client, current["headers"]["beta"])
    foreign_asset = upload_asset(client, current["headers"]["beta"], foreign_campaign["id"])
    with owner.session_factory() as session:
        source = session.get(MediaAsset, UUID(foreign_asset["id"]))
        assert source
        source.retention_deadline = utcnow() - timedelta(minutes=1)
        session.commit()
    database = Database(
        current["retention_settings"].database_url, runtime_role="vouch_retention"
    )
    try:
        with database.session_factory() as session:
            assert not session.scalars(select(MediaAsset)).all()
            discovered = session.execute(
                text("select id, organization_id from vouch_private.retention_expired_assets(100)")
            ).all()
            assert (UUID(foreign_asset["id"]), BETA_ORG_ID) in discovered
            set_database_scope(
                session, organization_id=ACME_ORG_ID,
                retention_asset_id=UUID(active_asset["id"]),
            )
            assert not session.scalars(select(MediaAsset)).all()  # Unexpired is not authority.
            assert session.execute(
                text("update media_assets set filename='' where id=:id"),
                {"id": UUID(active_asset["id"])},
            ).rowcount == 0
            session.commit()
            assert not session.scalars(select(MediaAsset)).all()
        with database.session_factory() as session:
            assert not session.scalars(select(MediaAsset)).all()  # No pool-context leak.
            set_database_scope(
                session, organization_id=ACME_ORG_ID,
                retention_asset_id=UUID(foreign_asset["id"]),
            )
            assert not session.scalars(select(MediaAsset)).all()  # Cross-tenant anchor denied.
            assert session.execute(
                text("update media_assets set filename='' where id=:id"),
                {"id": UUID(foreign_asset["id"])},
            ).rowcount == 0
            with pytest.raises(DBAPIError):
                session.execute(text("insert into approvals(id) values (:id)"), {"id": uuid4()})
            session.rollback()
    finally:
        database.dispose()
        for _ in range(50):
            with owner.session_factory() as session:
                source = session.get(MediaAsset, UUID(foreign_asset["id"]))
                if source and source.deleted_at is not None:
                    break
            assert reconcile_once(current["retention"], current["store"])
        deleted = client.post(
            "/api/v1/deletion-requests",
            headers=current["headers"]["marketer"],
            json={"resource_type": "media_asset", "resource_id": active_asset["id"]},
        )
        assert deleted.status_code == 202 and deleted.json()["status"] == "completed"
