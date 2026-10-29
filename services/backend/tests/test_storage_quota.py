from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from test_workflow import MP4, NOTICE_ACKNOWLEDGMENT, create_campaign, upload_asset

from vouch_backend.auth import Principal, get_principal
from vouch_backend.models import (
    ConsentReceipt,
    DeletionRequest,
    MediaAsset,
    Membership,
    utcnow,
)
from vouch_backend.seed import ACME_ORG_ID, MARKETER_USER_ID

LIMIT = 500_000_000
MAX_UPLOAD = 5_000_000


def intent_payload(campaign_id: str) -> dict[str, object]:
    return {
        "campaign_id": campaign_id,
        "filename": "synthetic.mp4",
        "content_type": "video/mp4",
        "byte_size": len(MP4),
        "rights_attested": True,
        **NOTICE_ACKNOWLEDGMENT,
    }


def add_asset(
    client: TestClient,
    campaign_id: str,
    *,
    actual_bytes: int | None = MAX_UPLOAD,
    deleted: bool = False,
    backend: str = "supabase",
) -> UUID:
    """Accounting metadata only: never allocate hundreds of MB or call Storage in unit tests."""
    asset_id = uuid4()
    with client.app.state.database.session_factory() as session:
        session.add(
            MediaAsset(
                id=asset_id,
                organization_id=ACME_ORG_ID,
                campaign_id=UUID(campaign_id),
                uploader_user_id=MARKETER_USER_ID,
                filename="synthetic.mp4",
                proposed_content_type="video/mp4",
                expected_bytes=len(MP4),
                actual_bytes=actual_bytes,
                sha256="a" * 64 if actual_bytes else None,
                status="deleted" if deleted else "validated" if actual_bytes else "intent_created",
                upload_token_hash="b" * 64,
                finalize_token_hash="c" * 64,
                storage_backend=backend,
                object_key=f"{ACME_ORG_ID}/{campaign_id}/{asset_id}/source"
                if backend == "supabase"
                else None,
                rights_attested=True,
                created_at=utcnow() - timedelta(minutes=10),
                retention_deadline=utcnow() + timedelta(days=30),
                deleted_at=utcnow() if deleted else None,
            )
        )
        session.commit()
    return asset_id


def fill_known_bytes(client: TestClient, campaign_id: str, count: int) -> None:
    for _index in range(count):
        add_asset(client, campaign_id)


def test_usage_is_typed_private_and_readable_by_current_viewer(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    assert client.get("/api/v1/storage/usage").status_code == 401
    expected = {
        "limit_bytes": LIMIT,
        "used_bytes": 0,
        "reserved_bytes": 0,
        "pending_cleanup_bytes": 0,
        "available_bytes": LIMIT,
        "max_upload_bytes": MAX_UPLOAD,
        "storage_backend": "database",
    }
    result = client.get("/api/v1/storage/usage", headers=marketer_headers)
    assert result.status_code == 200, result.text
    assert result.json() == expected
    viewer = {**marketer_headers, "X-Fixture-User": "viewer@vouch.test"}
    assert client.get("/api/v1/storage/usage", headers=viewer).json() == expected
    campaign = create_campaign(client, marketer_headers)
    denied = client.post("/api/v1/uploads", headers=viewer, json=intent_payload(campaign["id"]))
    assert denied.status_code == 403


def test_intent_reserves_full_bucket_maximum_then_accepted_bytes_settle_without_reencoding(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    intent = client.post(
        "/api/v1/uploads", headers=marketer_headers, json=intent_payload(campaign["id"])
    )
    assert intent.status_code == 201, intent.text
    usage = client.get("/api/v1/storage/usage", headers=marketer_headers).json()
    assert usage["reserved_bytes"] == MAX_UPLOAD and usage["used_bytes"] == 0
    uploaded = client.put(
        intent.json()["content_url"],
        content=MP4,
        headers={"Content-Type": "video/mp4", "X-Upload-Token": intent.json()["upload_token"]},
    )
    assert uploaded.status_code == 200, uploaded.text
    usage = client.get("/api/v1/storage/usage", headers=marketer_headers).json()
    assert usage["used_bytes"] == len(MP4) and usage["reserved_bytes"] == 0
    assert usage["available_bytes"] == LIMIT - len(MP4)
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, UUID(intent.json()["upload_id"]))
        assert asset is not None and asset.object_bytes == MP4


def test_expired_unknown_upload_stays_reserved_and_deleted_unknown_copy_stays_pending(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    asset_id = add_asset(client, campaign["id"], actual_bytes=None)
    usage = client.get("/api/v1/storage/usage", headers=marketer_headers).json()
    assert usage["reserved_bytes"] == MAX_UPLOAD
    with client.app.state.database.session_factory() as session:
        asset = session.get(MediaAsset, asset_id)
        assert asset is not None
        asset.status = "deleted"
        asset.deleted_at = utcnow()
        session.commit()
    usage = client.get("/api/v1/storage/usage", headers=marketer_headers).json()
    assert usage["reserved_bytes"] == 0
    assert usage["pending_cleanup_bytes"] == MAX_UPLOAD
    assert usage["available_bytes"] == LIMIT - MAX_UPLOAD


@pytest.mark.parametrize("receipt_status", ["partial", "failed", "in_progress"])
def test_partial_or_failed_unrelated_destinations_never_free_storage(
    client: TestClient, marketer_headers: dict[str, str], receipt_status: str
) -> None:
    campaign = create_campaign(client, marketer_headers)
    asset_id = add_asset(client, campaign["id"], actual_bytes=72, deleted=True)
    with client.app.state.database.session_factory() as session:
        session.add(
            DeletionRequest(
                organization_id=ACME_ORG_ID,
                resource_type="media_asset",
                resource_id=asset_id,
                status=receipt_status,
                requested_by=MARKETER_USER_ID,
                destinations=[
                    {"destination": "local_fixture_database", "status": "completed"},
                    {
                        "destination": "local_media_sandbox",
                        "status": "completed",
                        "asset_ids": [str(asset_id)],
                    },
                    {
                        "destination": "supabase_storage",
                        "status": "retry_pending",
                        "asset_ids": [str(asset_id)],
                    },
                ],
            )
        )
        session.commit()
    usage = client.get("/api/v1/storage/usage", headers=marketer_headers).json()
    assert usage["pending_cleanup_bytes"] == 72
    assert usage["used_bytes"] == 0 and usage["reserved_bytes"] == 0


def test_only_completed_storage_destination_bound_to_exact_asset_frees_bytes(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    erased = add_asset(client, campaign["id"], actual_bytes=20, deleted=True)
    pending = add_asset(client, campaign["id"], actual_bytes=30, deleted=True)
    with client.app.state.database.session_factory() as session:
        session.add_all(
            [
                DeletionRequest(
                    organization_id=ACME_ORG_ID,
                    resource_type="media_asset",
                    resource_id=erased,
                    status="partial",
                    requested_by=MARKETER_USER_ID,
                    destinations=[
                        {
                            "destination": "supabase_storage",
                            "status": "completed",
                            "asset_ids": [str(erased)],
                        },
                        {
                            "destination": "local_media_sandbox",
                            "status": "retry_pending",
                            "asset_ids": [str(erased)],
                        },
                    ],
                ),
                # A completed destination referencing another target cannot free this source.
                DeletionRequest(
                    organization_id=ACME_ORG_ID,
                    resource_type="media_asset",
                    resource_id=erased,
                    status="completed",
                    requested_by=MARKETER_USER_ID,
                    destinations=[
                        {
                            "destination": "supabase_storage",
                            "status": "completed",
                            "asset_ids": [str(pending)],
                        }
                    ],
                ),
            ]
        )
        session.commit()
    usage = client.get("/api/v1/storage/usage", headers=marketer_headers).json()
    assert usage["pending_cleanup_bytes"] == 30
    assert usage["available_bytes"] == LIMIT - 30


def test_storage_usage_is_scoped_to_current_tenant(
    client: TestClient, marketer_headers: dict[str, str], beta_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    upload_asset(client, marketer_headers, campaign["id"])
    assert client.get("/api/v1/storage/usage", headers=marketer_headers).json()[
        "used_bytes"
    ] == len(MP4)
    beta = client.get("/api/v1/storage/usage", headers=beta_headers)
    assert beta.status_code == 200
    assert beta.json()["used_bytes"] == 0 and beta.json()["available_bytes"] == LIMIT


def test_full_allowance_blocks_intent_without_new_asset_or_consent(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    fill_known_bytes(client, campaign["id"], 99)
    first = client.post(
        "/api/v1/uploads", headers=marketer_headers, json=intent_payload(campaign["id"])
    )
    assert first.status_code == 201, first.text
    denied = client.post(
        "/api/v1/uploads", headers=marketer_headers, json=intent_payload(campaign["id"])
    )
    assert denied.status_code == 409
    assert denied.json()["error"]["code"] == "STORAGE_ALLOWANCE_EXCEEDED"
    usage = client.get("/api/v1/storage/usage", headers=marketer_headers).json()
    assert usage["used_bytes"] == LIMIT - MAX_UPLOAD
    assert usage["reserved_bytes"] == MAX_UPLOAD and usage["available_bytes"] == 0
    with client.app.state.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 100
        assert session.scalar(select(func.count()).select_from(ConsentReceipt)) == 1


def test_stale_member_snapshot_cannot_create_intent_after_revocation(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    campaign = create_campaign(client, marketer_headers)
    stale = Principal(
        ACME_ORG_ID,
        "Acme",
        MARKETER_USER_ID,
        "marketer@vouch.test",
        "Mira",
        frozenset({"marketer"}),
    )
    with client.app.state.database.session_factory() as session:
        membership = session.scalar(
            select(Membership).where(Membership.user_id == MARKETER_USER_ID)
        )
        assert membership is not None
        membership.active = False
        session.commit()
    client.app.dependency_overrides[get_principal] = lambda: stale
    denied = client.post("/api/v1/uploads", json=intent_payload(campaign["id"]))
    assert denied.status_code == 403
    with client.app.state.database.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaAsset)) == 0


def test_concurrent_postgres_uploads_cannot_reserve_same_remaining_space(
    client: TestClient, marketer_headers: dict[str, str]
) -> None:
    if client.app.state.database.is_sqlite:
        pytest.skip("PostgreSQL advisory-lock proof; SQLite serializes fixture writes.")
    campaign = create_campaign(client, marketer_headers)
    fill_known_bytes(client, campaign["id"], 99)

    def reserve(_index: int) -> int:
        return client.post(
            "/api/v1/uploads", headers=marketer_headers, json=intent_payload(campaign["id"])
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(reserve, range(2)))
    assert sorted(statuses) == [201, 409]
    usage = client.get("/api/v1/storage/usage", headers=marketer_headers).json()
    assert usage["used_bytes"] + usage["reserved_bytes"] == LIMIT
