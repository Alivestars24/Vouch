"""Conservative workspace source-byte accounting, derived from existing durable lineage."""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import Principal
from .models import DeletionRequest, MediaAsset, SubmissionVersion
from .schemas import StorageUsageResponse
from .storage import MAX_MEDIA_BYTES

WORKSPACE_STORAGE_LIMIT_BYTES = 500_000_000


def _confirmed_storage_erasure(
    session: Session, organization_id: UUID, deleted_remote_ids: set[UUID]
) -> set[UUID]:
    if not deleted_remote_ids:
        return set()
    receipts = session.execute(
        select(
            DeletionRequest.resource_type,
            DeletionRequest.resource_id,
            DeletionRequest.destinations,
        ).where(
            DeletionRequest.organization_id == organization_id,
            DeletionRequest.status.in_(["completed", "partial", "failed", "in_progress"]),
        )
    ).all()
    submissions = {row.resource_id for row in receipts if row.resource_type == "submission"}
    submission_assets: dict[UUID, set[UUID]] = defaultdict(set)
    if submissions:
        for submission_id, asset_id in session.execute(
            select(SubmissionVersion.submission_id, SubmissionVersion.asset_id).where(
                SubmissionVersion.organization_id == organization_id,
                SubmissionVersion.submission_id.in_(submissions),
                SubmissionVersion.asset_id.in_(deleted_remote_ids),
            )
        ):
            submission_assets[submission_id].add(asset_id)
    confirmed: set[UUID] = set()
    for row in receipts:
        if row.resource_type == "media_asset":
            allowed = {row.resource_id} & deleted_remote_ids
        elif row.resource_type == "submission":
            allowed = submission_assets[row.resource_id]
        else:
            continue
        if not isinstance(row.destinations, list):
            continue
        for destination in row.destinations:
            if (
                not isinstance(destination, dict)
                or destination.get("destination") != "supabase_storage"
                or destination.get("status") != "completed"
                or not isinstance(destination.get("asset_ids"), list)
            ):
                continue
            # Destination JSON alone is not proof that a receipt owns another asset.
            confirmed.update(
                asset_id for asset_id in allowed if str(asset_id) in destination["asset_ids"]
            )
    return confirmed


def workspace_storage_usage_for(
    session: Session,
    organization_id: UUID,
    storage_backend: str,
) -> StorageUsageResponse:
    # Project only accounting metadata, never load media blobs/captions into the meter.
    assets = session.execute(
        select(
            MediaAsset.id,
            MediaAsset.storage_backend,
            MediaAsset.actual_bytes,
            MediaAsset.status,
            MediaAsset.deleted_at,
            MediaAsset.object_bytes.is_not(None).label("has_database_bytes"),
        ).where(MediaAsset.organization_id == organization_id)
    ).all()
    deleted_remote = {
        row.id
        for row in assets
        if row.storage_backend == "supabase"
        and (row.deleted_at is not None or row.status == "deleted")
    }
    confirmed = _confirmed_storage_erasure(session, organization_id, deleted_remote)
    used = reserved = pending = 0
    for row in assets:
        accepted_bytes = (
            row.actual_bytes if isinstance(row.actual_bytes, int) and row.actual_bytes > 0 else None
        )
        if row.deleted_at is not None or row.status == "deleted":
            if row.storage_backend == "supabase":
                if row.id not in confirmed:
                    pending += accepted_bytes or MAX_MEDIA_BYTES
            elif row.storage_backend != "database" or row.has_database_bytes:
                pending += accepted_bytes or MAX_MEDIA_BYTES
        elif accepted_bytes is not None and row.status != "intent_created":
            used += accepted_bytes
        else:
            # Storage clients can bypass API PUT but not the private bucket's 5 MB cap.
            # Never reserve only their declared size or free unknown outcomes on expiry.
            reserved += MAX_MEDIA_BYTES
    return StorageUsageResponse(
        limit_bytes=WORKSPACE_STORAGE_LIMIT_BYTES,
        used_bytes=used,
        reserved_bytes=reserved,
        pending_cleanup_bytes=pending,
        available_bytes=max(0, WORKSPACE_STORAGE_LIMIT_BYTES - used - reserved - pending),
        max_upload_bytes=MAX_MEDIA_BYTES,
        storage_backend="supabase" if storage_backend == "supabase" else "database",
    )


def workspace_storage_usage(session: Session, principal: Principal) -> StorageUsageResponse:
    return workspace_storage_usage_for(
        session,
        principal.organization_id,
        "supabase" if principal.access_token else "database",
    )
