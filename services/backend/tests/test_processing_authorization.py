from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_media_finalization import finalize, uploaded
from test_storage import MemoryStore
from test_workflow import (
    MP4,
    NOTICE_ACKNOWLEDGMENT,
    create_campaign,
    create_submission,
    start_check,
)

from vouch_backend import service
from vouch_backend.media import FixtureMediaProcessor, PreparedMedia, ProcessedMedia
from vouch_backend.models import (
    Analysis,
    Approval,
    AuditEvent,
    Campaign,
    ConsentReceipt,
    DeletionRequest,
    Job,
    MediaAsset,
    Organization,
    RulePackVersion,
    SubmissionVersion,
    utcnow,
)
from vouch_backend.notices import CURRENT_NOTICE, get_notice
from vouch_backend.retention import reconcile_once
from vouch_backend.schemas import CheckCreate
from vouch_backend.seed import ACME_ORG_ID, MARKETER_USER_ID
from vouch_backend.worker import process_next_job


def intake(campaign_id: str) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id, "filename": "authorized.mp4", "content_type": "video/mp4",
        "byte_size": len(MP4), "rights_attested": True, **NOTICE_ACKNOWLEDGMENT,
    }


def test_public_notice_is_immutable_versioned_and_explicitly_a_local_draft(
    client: TestClient,
) -> None:
    current = client.get("/api/v1/notices/campaign-check")
    assert current.status_code == 200
    notice = current.json()
    assert notice["purpose"] == "campaign_check" and notice["status"] == "draft_local_only"
    assert notice["notice_hash"] == hashlib.sha256(notice["body"].encode()).hexdigest()
    assert client.get(f"/api/v1/notices/campaign-check/{notice['version']}").json() == notice
    assert client.get("/api/v1/notices/campaign-check/unknown").status_code == 404
    assert get_notice().body == CURRENT_NOTICE.body
    with pytest.raises(ValueError):
        CURRENT_NOTICE.body = "cannot rewrite the notice"  # type: ignore[misc]


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("notice_version", None, 422), ("notice_acknowledged", None, 422),
        ("purpose", None, 422), ("notice_acknowledged", False, 422),
        ("notice_acknowledged", 1, 422), ("purpose", "try_preview", 422),
        ("notice_version", "prior-or-unknown-version", 409),
    ],
)
def test_intake_requires_separate_current_affirmative_processing_authorization(
    client: TestClient, marketer_headers: dict[str, str], field: str, value: object, expected: int
) -> None:
    campaign = create_campaign(client, marketer_headers)
    payload = intake(campaign["id"])
    if value is None:
        del payload[field]
    else:
        payload[field] = value
    response = client.post("/api/v1/uploads", headers=marketer_headers, json=payload)
    assert response.status_code == expected, response.text
    if expected == 409:
        assert response.json()["error"]["code"] == "NOTICE_VERSION_STALE"
    with client.app.state.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 0
        assert session.scalar(select(func.count()).select_from(ConsentReceipt)) == 0


def test_upload_receipt_is_atomic_verified_attribution_not_client_supplied_metadata(
    client: TestClient, marketer_headers: dict[str, str], reviewer_headers: dict[str, str],
    beta_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign = create_campaign(client, marketer_headers)
    payload = intake(campaign["id"])
    forged = client.post(
        "/api/v1/uploads", headers=marketer_headers,
        json={**payload, "actor_user_id": str(uuid4())},
    )
    assert forged.status_code == 422
    original_audit = service.audit

    def interrupted(*args: Any, **kwargs: Any) -> None:
        if args[2] == "processing.authorization_acknowledged":
            raise RuntimeError("controlled interruption after receipt insertion")
        original_audit(*args, **kwargs)

    monkeypatch.setattr(service, "audit", interrupted)
    with pytest.raises(RuntimeError, match="controlled interruption"):
        client.post("/api/v1/uploads", headers=marketer_headers, json=payload)
    with client.app.state.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 0
        assert session.scalar(select(func.count()).select_from(ConsentReceipt)) == 0
    monkeypatch.setattr(service, "audit", original_audit)
    accepted = client.post("/api/v1/uploads", headers=marketer_headers, json=payload)
    assert accepted.status_code == 201, accepted.text
    item = accepted.json()
    receipt = item["consent_receipt"]
    assert item["authorization_status"] == "active"
    assert receipt["actor_user_id"] == str(MARKETER_USER_ID)
    assert receipt["asset_id"] == item["upload_id"] and receipt["campaign_id"] == campaign["id"]
    assert receipt["notice_hash"] == CURRENT_NOTICE.notice_hash and receipt["accepted_at"]
    assert receipt["revoked_at"] is None
    url = f"/api/v1/consent-receipts/{receipt['id']}"
    assert client.get(url, headers=reviewer_headers).json() == receipt
    assert client.get(url, headers=beta_headers).status_code == 404
    assert client.post(f"{url}/withdraw", headers=reviewer_headers).status_code == 403
    assert client.post(f"{url}/withdraw", headers=beta_headers).status_code == 404


def test_new_manifest_binds_receipt_but_legacy_history_is_not_rewritten(
    client: TestClient, marketer_headers: dict[str, str], reviewer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version = submission["versions"][0]
    assert version["authorization_status"] == "active"
    accepted = start_check(client, marketer_headers, version["id"], "clean", uuid4().hex)
    assert accepted.status_code == 202 and process_next_job(client.app.state.database)
    check_url = f"/api/v1/checks/{accepted.json()['resource_id']}"
    check = client.get(check_url, headers=reviewer_headers).json()
    approved = client.post(
        f"{check_url}/review-decisions", headers=reviewer_headers,
        json={"action": "approve", "expected_review_version": 1,
              "manifest_hash": check["manifest_hash"], "rationale": "Exact authorized version."},
    )
    assert approved.status_code == 200
    with client.app.state.database.session_factory() as session:
        receipt = session.get(ConsentReceipt, UUID(version["consent_receipt"]["id"]))
        assert receipt
        stored_version = session.get(SubmissionVersion, UUID(version["id"]))
        stored_campaign = session.get(Campaign, UUID(campaign["id"]))
        assert stored_version and stored_campaign
        asset = session.get(MediaAsset, stored_version.asset_id)
        pack = session.get(RulePackVersion, stored_campaign.rule_pack_version_id)
        assert asset and pack
        manifest = service._manifest(
            stored_version, asset, stored_campaign, pack, CheckCreate(scenario="clean"), receipt
        )
        assert manifest["processing_authorization"] == {
            "receipt_id": str(receipt.id), "purpose": "campaign_check",
            "notice_version": receipt.notice_version, "notice_hash": receipt.notice_hash,
        }
        assert service.stable_hash(manifest) == check["manifest_hash"]
        assert service.stable_hash({
            key: value for key, value in manifest.items() if key != "processing_authorization"
        }) != check["manifest_hash"]
        # Simulate an existing pre-cutover asset; never manufacture a backfilled acknowledgment.
        session.delete(receipt)
        session.commit()
        analysis = session.get(Analysis, UUID(check["id"]))
        assert analysis and analysis.manifest_hash == check["manifest_hash"]
        assert session.scalar(select(Approval).where(Approval.analysis_id == analysis.id))
    history = client.get(f"/api/v1/submissions/{submission['id']}", headers=marketer_headers)
    assert history.status_code == 200
    legacy = history.json()["versions"][0]
    assert legacy["authorization_status"] == "legacy_no_notice"
    assert legacy["consent_receipt"] is None
    historical = client.get(check_url, headers=reviewer_headers)
    assert historical.status_code == 200 and historical.json()["approval"]
    assert historical.json()["manifest_hash"] == check["manifest_hash"]
    refused = start_check(client, marketer_headers, version["id"], "success", uuid4().hex)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "PROCESSING_AUTHORIZATION_REQUIRED"
    attach = client.post(
        f"/api/v1/campaigns/{campaign['id']}/submissions", headers=marketer_headers,
        json={"asset_id": version["asset_id"], "creator_id": campaign["creator_ids"][0],
              "caption": "Cannot reuse legacy authorization", "rights_attested": True},
    )
    assert attach.status_code == 409
    rejected = client.post(
        f"{check_url}/review-decisions", headers=reviewer_headers,
        json={"action": "reject", "expected_review_version": 2,
              "manifest_hash": check["manifest_hash"], "rationale": "New decision is blocked."},
    )
    assert rejected.status_code == 409
    revoked = client.post(
        f"{check_url}/review-decisions", headers=reviewer_headers,
        json={"action": "revoke", "expected_review_version": 2,
              "manifest_hash": check["manifest_hash"], "rationale": "Revoke historical approval."},
    )
    assert revoked.status_code == 200 and revoked.json()["review_status"] == "revoked"


def test_withdrawal_fences_work_and_retries_the_same_incomplete_deletion_without_reactivation(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version = submission["versions"][0]
    accepted = start_check(client, marketer_headers, version["id"], "success", uuid4().hex)
    assert accepted.status_code == 202
    store = MemoryStore()
    client.app.state.media_store = store
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(version["asset_id"]))
        assert asset
        deadline = asset.retention_deadline
        asset.storage_backend = "supabase"
        asset.object_key = f"{asset.organization_id}/{asset.campaign_id}/{asset.id}/source"
        store.objects[asset.object_key] = MP4
        session.commit()
    url = f"/api/v1/consent-receipts/{version['consent_receipt']['id']}"
    first = client.post(f"{url}/withdraw", headers=marketer_headers)
    assert first.status_code == 202 and first.json()["status"] == "partial"
    withdrawn = client.get(url, headers=marketer_headers).json()
    assert withdrawn["revoked_at"] and withdrawn["revoked_by"] == str(MARKETER_USER_ID)
    assert withdrawn["revocation_actor_kind"] == "member"
    assert withdrawn["revocation_reason"] == "withdrawn"
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(version["asset_id"]))
        assert asset and asset.retention_deadline == deadline and asset.deleted_at
        organization = session.get(Organization, ACME_ORG_ID)
        assert organization and organization.budget_held_minor == 0
        job = session.get(Job, UUID(accepted.json()["operation_id"]))
        assert job and job.status == "cancelled" and job.fence > 0
    store.fail_delete = False
    completed = client.post(f"{url}/withdraw", headers=marketer_headers)
    assert completed.status_code == 202 and completed.json()["status"] == "completed"
    assert completed.json()["id"] == first.json()["id"]
    assert client.get(url, headers=marketer_headers).json() == withdrawn
    assert not store.objects
    with client.app.state.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(DeletionRequest)) == 1


@pytest.mark.parametrize("expiry", [False, True], ids=["member-delete", "system-expiry"])
def test_every_erasure_revokes_authorization_with_truthful_attribution(
    client: TestClient, marketer_headers: dict[str, str], expiry: bool
) -> None:
    campaign = create_campaign(client, marketer_headers)
    submission = create_submission(client, marketer_headers, campaign)
    version = submission["versions"][0]
    if expiry:
        with client.app.state.database.session_factory() as session:
            asset = session.get(MediaAsset, UUID(version["asset_id"]))
            assert asset
            asset.retention_deadline = utcnow() - timedelta(seconds=1)
            session.commit()
        assert reconcile_once(client.app.state.database)
    else:
        deleted = client.post(
            "/api/v1/deletion-requests", headers=marketer_headers,
            json={"resource_type": "submission", "resource_id": submission["id"]},
        )
        assert deleted.status_code == 202 and deleted.json()["status"] == "completed"
    url = f"/api/v1/consent-receipts/{version['consent_receipt']['id']}"
    receipt = client.get(url, headers=marketer_headers).json()
    assert receipt["revocation_reason"] == ("expired" if expiry else "source_deleted")
    assert receipt["revocation_actor_kind"] == ("retention" if expiry else "member")
    assert receipt["revoked_by"] == (None if expiry else str(MARKETER_USER_ID))
    with client.app.state.database.session_factory() as session:
        event = session.scalar(select(AuditEvent).where(
            AuditEvent.action == "processing.authorization_revoked",
            AuditEvent.resource_id == UUID(receipt["id"]),
        ))
        assert event and event.actor_kind == receipt["revocation_actor_kind"]
        assert event.actor_user_id == (None if expiry else MARKETER_USER_ID)


def test_withdrawal_during_decoding_wins_late_publication(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    entered, release = Event(), Event()

    class Paused(FixtureMediaProcessor):
        def process(
            self, body: bytes, content_type: str, prepared: PreparedMedia | None = None
        ) -> ProcessedMedia:
            entered.set()
            assert release.wait(10)
            return super().process(body, content_type, prepared)

    client.app.state.media_processor = Paused()
    _, intent = uploaded(client, marketer_headers)
    url = f"/api/v1/consent-receipts/{intent['consent_receipt']['id']}/withdraw"
    with ThreadPoolExecutor(max_workers=2) as executor:
        processing = executor.submit(finalize, client, marketer_headers, intent)
        try:
            assert entered.wait(5)
            withdrawn = client.post(url, headers=marketer_headers)
            assert withdrawn.status_code == 202 and withdrawn.json()["status"] == "completed"
        finally:
            release.set()
        assert processing.result(timeout=5).status_code == 404
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent["upload_id"]))
        receipt = session.get(ConsentReceipt, UUID(intent["consent_receipt"]["id"]))
        assert asset and asset.status == "deleted" and asset.processing_metadata == {}
        assert receipt and receipt.revocation_reason == "withdrawn"
