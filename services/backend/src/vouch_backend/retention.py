"""Anchored source expiration and durable exact-key cleanup; no model calls."""

from __future__ import annotations

import logging
import socket
import time
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session

from .config import Settings
from .db import Database, set_database_scope
from .models import DeletionRequest, GuestExchangeAttempt, MediaAsset, utcnow
from .schemas import DeletionRequestCreate
from .service import RetentionActor, _erase_source, _finish_storage_deletion
from .storage import MediaStore, SupabaseMediaStore

LOGGER = logging.getLogger("vouch.retention")


def _prune_guest_exchange_attempts(session: Session, restricted: bool) -> int:
    if restricted:
        result = session.scalar(text("select vouch_private.prune_guest_exchange_attempts()"))
        return int(result or 0)
    result = session.execute(
        delete(GuestExchangeAttempt).where(
            GuestExchangeAttempt.attempted_at < utcnow() - timedelta(hours=24)
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def _discover(session: Session, restricted: bool, receipts: bool) -> tuple[UUID, UUID] | None:
    if restricted:
        # Private metadata-only discovery. No system SELECT * across tenants.
        function = "retention_pending_requests" if receipts else "retention_expired_assets"
        row = session.execute(
            text(f"select id, organization_id from vouch_private.{function}(1)")
        ).first()
    elif receipts:
        now = utcnow()
        row = session.execute(
            select(DeletionRequest.id, DeletionRequest.organization_id)
            .where(
                DeletionRequest.status.not_in(["completed", "failed"]),
                or_(DeletionRequest.retry_after.is_(None), DeletionRequest.retry_after <= now),
                or_(DeletionRequest.lease_until.is_(None), DeletionRequest.lease_until <= now),
            )
            .order_by(DeletionRequest.created_at, DeletionRequest.id)
            .limit(1)
        ).first()
    else:
        row = session.execute(
            select(MediaAsset.id, MediaAsset.organization_id)
            .where(
                MediaAsset.retention_deadline <= utcnow(),
                MediaAsset.deleted_at.is_(None),
                MediaAsset.status != "deleted",
            )
            .order_by(MediaAsset.retention_deadline, MediaAsset.id)
            .limit(1)
        ).first()
    return (row[0], row[1]) if row else None


def reconcile_once(
    database: Database,
    media_store: MediaStore | None = None,
    *,
    worker_id: str = "retention-worker",
) -> bool:
    """Do at most one stored expiry/receipt. A later invocation safely resumes interrupted work."""
    with database.session_factory() as session:
        session.info["media_store"] = media_store
        restricted = database.runtime_role == "vouch_retention"
        pruned_attempts = _prune_guest_exchange_attempts(session, restricted)
        session.commit()
        candidate = _discover(session, restricted, receipts=True)
        if candidate:
            request_id, org_id = candidate
            set_database_scope(
                session, organization_id=org_id, retention_request_id=request_id,
            )
            receipt = session.get(DeletionRequest, request_id)
        else:
            candidate = _discover(session, restricted, receipts=False)
            if candidate is None:
                return pruned_attempts > 0
            asset_id, org_id = candidate
            set_database_scope(session, organization_id=org_id, retention_asset_id=asset_id)
            receipt = _erase_source(
                session, RetentionActor(org_id),
                DeletionRequestCreate(resource_type="media_asset", resource_id=asset_id),
            )
            set_database_scope(session, retention_request_id=receipt.id)
        if receipt is not None:
            _finish_storage_deletion(
                session, RetentionActor(org_id), receipt,
                automatic=True, worker_id=worker_id,
            )
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    database = Database(
        settings.database_url, settings.database_schema,
        runtime_role="vouch_retention" if settings.auth_mode == "supabase" else None,
    )
    database.create_all()
    store = SupabaseMediaStore(settings) if settings.auth_mode == "supabase" else None
    worker_id = f"retention-{socket.gethostname()}-{id(database)}"
    LOGGER.info("Vouch local retention process started")
    try:
        while True:
            try:
                processed = reconcile_once(database, store, worker_id=worker_id)
            except Exception:
                # Omit exception payload/SQL parameters: credentials/content stay private.
                LOGGER.error("Retention cycle failed safely; durable work will be retried")
                processed = False
            if not processed:
                time.sleep(max(1.0, settings.worker_poll_seconds))
    except KeyboardInterrupt:
        LOGGER.info("Vouch retention process stopped")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
