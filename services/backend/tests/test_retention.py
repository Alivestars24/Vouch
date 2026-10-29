from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_storage import MemoryStore
from test_workflow import MP4, create_campaign, create_submission, start_check

from vouch_backend.db import Database
from vouch_backend.models import (
    AuditEvent,
    DeletionRequest,
    EvidenceItem,
    Finding,
    GuestExchangeAttempt,
    Job,
    MediaAsset,
    Organization,
    ReviewContext,
    SubmissionVersion,
    utcnow,
)
from vouch_backend.retention import reconcile_once
from vouch_backend.schemas import DeletionRequestCreate
from vouch_backend.service import RetentionActor, _claim_deletion, _erase_source
from vouch_backend.worker import process_next_job


def test_retention_prunes_guest_exchange_privacy_buckets_without_future_traffic(
    client: TestClient,
) -> None:
    database = client.app.state.database
    with database.session_factory() as session:
        session.add_all(
            [
                GuestExchangeAttempt(
                    client_bucket_hash="a" * 64,
                    token_digest="b" * 64,
                    attempted_at=utcnow() - timedelta(hours=24, seconds=1),
                ),
                GuestExchangeAttempt(
                    client_bucket_hash="c" * 64,
                    token_digest="d" * 64,
                    attempted_at=utcnow(),
                ),
            ]
        )
        session.commit()

    assert reconcile_once(database)
    with database.session_factory() as session:
        attempts = session.scalars(select(GuestExchangeAttempt)).all()
        assert [(item.client_bucket_hash, item.token_digest) for item in attempts] == [
            ("c" * 64, "d" * 64)
        ]
    assert not reconcile_once(database)


def expire(database: Database, asset_id: str, store: MemoryStore | None = None) -> None:
    with database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(asset_id))
        assert asset is not None
        asset.retention_deadline = utcnow() - timedelta(seconds=1)
        if store is not None:
            asset.storage_backend = "supabase"
            asset.object_key = f"{asset.organization_id}/{asset.campaign_id}/{asset.id}/source"
            asset.object_bytes = None
            store.objects[asset.object_key] = MP4
        session.commit()


def receipt(database: Database) -> DeletionRequest:
    with database.session_factory() as session:
        result = session.scalar(select(DeletionRequest))
        assert result is not None
        return result


def make_due(database: Database) -> None:
    with database.session_factory() as session:
        result = session.scalar(select(DeletionRequest))
        assert result is not None
        result.retry_after = utcnow() - timedelta(seconds=1)
        result.lease_until = utcnow() - timedelta(seconds=1)
        session.commit()


@pytest.mark.parametrize("stage", ["queued", "completed"])
def test_expiry_scrubs_derivatives_without_human_impersonation(
    client: TestClient, marketer_headers: dict[str, str], stage: str,
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version = submission["versions"][0]
    accepted = start_check(client, marketer_headers, version["id"], "success", "expiry")
    assert accepted.status_code == 202
    database = client.app.state.database
    if stage == "completed":
        assert process_next_job(database)
    expire(database, version["asset_id"])
    with database.session_factory() as session:
        before = session.get(MediaAsset, UUID(version["asset_id"]))
        assert before is not None
        deadline = before.retention_deadline
    assert reconcile_once(database)
    assert not reconcile_once(database)
    result = receipt(database)
    assert result.status == "completed" and result.completed_at is not None
    assert result.requested_by is None and result.requested_by_kind == "retention"
    with database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(version["asset_id"]))
        assert asset is not None and asset.status == "deleted" and asset.object_bytes is None
        assert asset.retention_deadline == deadline and asset.filename == ""
        assert all(v.caption == "" for v in session.scalars(select(SubmissionVersion)))
        assert all(v.description == "" for v in session.scalars(select(EvidenceItem)))
        assert all(v.evidence_text == "" for v in session.scalars(select(Finding)))
        assert all(v.review_status == "revoked" for v in session.scalars(select(ReviewContext)))
        org = session.get(Organization, asset.organization_id)
        assert org is not None and org.budget_held_minor == 0
        if stage == "queued":
            job = session.scalar(select(Job))
            assert job is not None and job.status == "cancelled" and job.fence > 0
        events = session.scalars(select(AuditEvent).where(
            AuditEvent.resource_type == "deletion_request",
        )).all()
        assert events and all(
            e.actor_kind == "retention" and e.actor_user_id is None for e in events
        )
    history = client.get(
        f"/api/v1/deletion-requests?campaign_id={campaign['id']}", headers=marketer_headers,
    )
    assert history.status_code == 200 and history.json()["items"][0]["id"] == str(result.id)


def test_expired_abandoned_upload_is_cleaned_without_a_submission(
    client: TestClient, marketer_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    from test_workflow import NOTICE_ACKNOWLEDGMENT

    response = client.post("/api/v1/uploads", headers=marketer_headers, json={
        **NOTICE_ACKNOWLEDGMENT,
        "campaign_id": campaign["id"], "filename": "abandoned.mp4", "content_type": "video/mp4",
        "byte_size": len(MP4), "rights_attested": True,
    })
    assert response.status_code == 201
    database = client.app.state.database
    # Non-expired sources are never swept.
    assert not reconcile_once(database)
    expire(database, response.json()["upload_id"])
    assert reconcile_once(database)
    assert receipt(database).status == "completed"


def test_storage_retry_is_durable_bounded_and_explicitly_recoverable(
    client: TestClient, marketer_headers: dict[str, str], beta_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    asset_id = submission["versions"][0]["asset_id"]
    database = client.app.state.database
    store = MemoryStore()
    client.app.state.media_store = store
    expire(database, asset_id, store)
    assert reconcile_once(database, store)
    first = receipt(database)
    assert first.status == "partial" and first.attempt_count == 1 and first.retry_after
    assert first.completed_at is None and store.objects
    assert not reconcile_once(database, store)  # Backoff survives a new invocation.
    for _ in range(2):
        make_due(database)
        # New database/pool models a process restart; it must reuse the same receipt/deadline.
        restarted = Database(
            database.engine.url.render_as_string(hide_password=False), database.schema,
        )
        try:
            assert reconcile_once(restarted, store)
        finally:
            restarted.dispose()
    final = receipt(database)
    assert final.id == first.id and final.status == "failed" and final.attempt_count == 3
    assert final.completed_at is None and not reconcile_once(database, store)
    denied = client.get(f"/api/v1/deletion-requests/{final.id}", headers=beta_headers)
    assert denied.status_code == 404
    assert client.get("/api/v1/deletion-requests", headers=beta_headers).json() == {"items": []}
    store.fail_delete = False
    manual = client.post("/api/v1/deletion-requests", headers=marketer_headers, json={
        "resource_type": "media_asset", "resource_id": asset_id,
    })
    assert manual.status_code == 202, manual.text
    assert manual.json()["id"] == str(first.id) and manual.json()["status"] == "completed"
    assert not store.objects


def test_restart_after_erasure_and_concurrent_receipt_claims(
    client: TestClient, marketer_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    asset_id = submission["versions"][0]["asset_id"]
    database = client.app.state.database
    store = MemoryStore()
    expire(database, asset_id, store)
    with database.session_factory() as session:
        result = _erase_source(
            session, RetentionActor(UUID(marketer_headers["X-Organization-Id"])),
            DeletionRequestCreate(resource_type="media_asset", resource_id=UUID(asset_id)),
        )
    assert result.status == "partial" and result.attempt_count == 0

    def claim(index: int) -> Any:
        with database.session_factory() as session:
            return _claim_deletion(
                session, result.organization_id, result.id,
                automatic=True, worker_id=f"cleanup-{index}",
            )

    with ThreadPoolExecutor(max_workers=3) as pool:
        claims = list(pool.map(claim, range(3)))
    assert sum(item is not None for item in claims) == 1
    assert not reconcile_once(database, store)  # Live lease is not stolen.
    make_due(database)
    store.fail_delete = False
    assert reconcile_once(database, store)
    assert receipt(database).status == "completed" and not store.objects


def test_stale_remote_completion_cannot_overwrite_new_claim(
    client: TestClient, marketer_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    database = client.app.state.database
    store = MemoryStore()
    expire(database, submission["versions"][0]["asset_id"], store)

    class ReclaimDuringDelete(MemoryStore):
        def delete(self, key: str) -> None:
            make_due(database)
            current = receipt(database)
            with database.session_factory() as session:
                claimed = _claim_deletion(
                    session, current.organization_id, current.id,
                    automatic=True, worker_id="replacement",
                )
                assert claimed is not None and claimed.fence == 2
            store.objects.pop(key, None)

    assert reconcile_once(database, ReclaimDuringDelete())
    current = receipt(database)
    assert current.status == "in_progress" and current.fence == 2
    assert current.completed_at is None
    make_due(database)
    store.fail_delete = False
    assert reconcile_once(database, store)
    assert receipt(database).status == "completed"


def test_crash_on_final_attempt_expires_into_visible_failure_without_more_http(
    client: TestClient, marketer_headers: dict[str, str],
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    database = client.app.state.database
    store = MemoryStore()
    expire(database, submission["versions"][0]["asset_id"], store)
    assert reconcile_once(database, store)
    initial = receipt(database)
    for index in (2, 3):
        make_due(database)
        with database.session_factory() as session:
            claimed = _claim_deletion(
                session, initial.organization_id, initial.id,
                automatic=True, worker_id=f"crashing-{index}",
            )
            assert claimed is not None and claimed.attempt_count == index
    make_due(database)
    store.fail_delete = False
    assert reconcile_once(database, store)
    final = receipt(database)
    assert final.status == "failed" and final.attempt_count == 3 and final.completed_at is None
    assert final.last_error_code == "CLEANUP_RETRIES_EXHAUSTED"
    assert store.objects  # No unbudgeted fourth Storage call, even though it would now succeed.
    assert not reconcile_once(database, store)
