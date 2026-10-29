from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select, text, update
from sqlalchemy.orm import Session

from .auth import Principal, require_roles
from .config import Settings
from .errors import ApiError, conflict, forbidden, not_found, unprocessable
from .guest_auth import (
    GuestPrincipal,
    as_utc,
    guest_access_ended,
    guest_grant_is_authorized,
)
from .media import MediaProcessor, remove_sandbox_container
from .models import (
    Approval,
    Brand,
    Campaign,
    CampaignCreator,
    ConsentReceipt,
    Creator,
    CreatorFeedback,
    GuestCommand,
    GuestExchangeAttempt,
    GuestGrant,
    GuestSession,
    MediaAsset,
    Product,
    ReviewContext,
    Submission,
    SubmissionVersion,
    Tombstone,
)
from .notices import require_current_guest_notice
from .schemas import (
    DeletionRequestCreate,
    GuestInvitationCreate,
    GuestSubmissionVersionCreate,
    GuestUploadIntentCreate,
)
from .service import (
    _erase_source,
    _validate_staged_media,
    audit,
    deletion_dict,
    get_campaign,
    lock_lineage,
    sha256_bytes,
    sha256_text,
    source_authorization_active,
    source_expired,
    stable_hash,
)
from .storage import MAX_MEDIA_BYTES, GuestMediaStore
from .storage_quota import workspace_storage_usage_for

INVITATION_LIFETIME = timedelta(hours=48)
SESSION_LIFETIME = timedelta(minutes=30)
EXCHANGE_WINDOW = timedelta(minutes=15)
CLIENT_ATTEMPT_LIMIT = 10
TOKEN_ATTEMPT_LIMIT = 5
READ_ACTION = "read_submission"
UPLOAD_ACTION = "upload_source"
SUBMIT_ACTION = "submit_version"
MUTATION_ACTIONS = [READ_ACTION, UPLOAD_ACTION, SUBMIT_ACTION]
UPLOAD_LIFETIME = timedelta(minutes=5)
MAX_GRANT_SOURCES = 5
MAX_GRANT_BYTES = 25_000_000
UPLOAD_OPERATION = "guest_upload_intent"
VERSION_OPERATION = "guest_submission_version"


def _ordered_guest_actions(actions: list[str] | frozenset[str]) -> list[str]:
    return [action for action in MUTATION_ACTIONS if action in actions]


def require_guest_action(principal: GuestPrincipal, action: str) -> None:
    if action not in principal.allowed_actions:
        raise forbidden(
            "GUEST_ACTION_NOT_ALLOWED",
            "This creator invitation does not allow that action.",
        )


def _idempotency_key(value: str | None) -> str:
    key = value.strip() if value else ""
    if not key:
        raise unprocessable(
            "IDEMPOTENCY_KEY_REQUIRED",
            "Provide an Idempotency-Key for this creator command.",
        )
    if len(key) > 160:
        raise unprocessable(
            "IDEMPOTENCY_KEY_INVALID",
            "Idempotency-Key must contain at most 160 characters.",
        )
    return key


def _capability_token(
    settings: Settings,
    label: str,
    asset_id: UUID,
    guest_session_id: UUID,
) -> str:
    digest = hmac.new(
        settings.guest_rate_limit_key.encode("utf-8"),
        f"vouch.guest.{label}.{guest_session_id}.{asset_id}".encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _guest_command(
    session: Session,
    principal: GuestPrincipal,
    operation: str,
    idempotency_key: str,
) -> GuestCommand | None:
    return session.scalar(
        select(GuestCommand)
        .where(
            GuestCommand.organization_id == principal.organization_id,
            GuestCommand.guest_session_id == principal.session_id,
            GuestCommand.operation == operation,
            GuestCommand.idempotency_key == idempotency_key,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _assert_command_digest(command: GuestCommand, request_digest: str) -> None:
    if not secrets.compare_digest(command.request_digest, request_digest):
        raise conflict(
            "IDEMPOTENCY_KEY_REUSED",
            "That Idempotency-Key was already used with a different request.",
        )


def _uses_guest_runtime_role(session: Session) -> bool:
    return (
        session.get_bind().dialect.name == "postgresql"
        and session.scalar(text("select current_user")) == "vouch_guest"
    )


def _guest_grant_authorized_for_mutation(
    session: Session,
    grant: GuestGrant,
    now: datetime,
) -> bool:
    if _uses_guest_runtime_role(session):
        return session.scalar(text("select vouch_private.guest_scope_active()")) is True
    return guest_grant_is_authorized(session, grant, now, require_consumed=True)


def _current_guest_scope(
    session: Session,
    principal: GuestPrincipal,
    action: str,
    *,
    lock_submission: bool,
) -> tuple[GuestGrant, GuestSession, Submission]:
    require_guest_action(principal, action)
    now = datetime.now(UTC)
    guest_session_query = select(GuestSession).where(
        GuestSession.id == principal.session_id,
        GuestSession.organization_id == principal.organization_id,
        GuestSession.grant_id == principal.grant_id,
    )
    if lock_submission:
        guest_session_query = guest_session_query.with_for_update()
    guest_session = session.scalar(
        guest_session_query.execution_options(populate_existing=True)
    )
    if (
        guest_session is None
        or guest_session.revoked_at is not None
        or as_utc(guest_session.expires_at) <= now
    ):
        raise guest_access_ended()
    grant_query = select(GuestGrant).where(
        GuestGrant.id == principal.grant_id,
        GuestGrant.organization_id == principal.organization_id,
    )
    if lock_submission:
        grant_query = grant_query.with_for_update()
    grant = session.scalar(grant_query.execution_options(populate_existing=True))
    if (
        grant is None
        or grant.campaign_id != principal.campaign_id
        or grant.creator_id != principal.creator_id
        or grant.submission_id != principal.submission_id
        or not _guest_grant_authorized_for_mutation(session, grant, now)
    ):
        raise guest_access_ended()
    if action not in grant.allowed_actions:
        raise forbidden(
            "GUEST_ACTION_NOT_ALLOWED",
            "This creator invitation does not allow that action.",
        )
    submission_query = select(Submission).where(
        Submission.id == principal.submission_id,
        Submission.organization_id == principal.organization_id,
        Submission.campaign_id == principal.campaign_id,
        Submission.creator_id == principal.creator_id,
        Submission.deleted_at.is_(None),
    )
    if lock_submission:
        submission_query = submission_query.with_for_update()
    submission = session.scalar(
        submission_query.execution_options(populate_existing=True)
    )
    if submission is None:
        raise guest_access_ended()
    return grant, guest_session, submission


def _require_guest_runtime(settings: Settings) -> None:
    if settings.auth_mode == "supabase" and settings.guest_database_url is None:
        raise ApiError(
            503,
            "GUEST_RUNTIME_UNAVAILABLE",
            "Creator access is not configured for this environment.",
            True,
        )


def _require_grant_issuer_role(principal: Principal, scope_kind: str) -> None:
    if scope_kind == "created_submission":
        require_roles(principal, "admin", "marketer")
    else:
        require_roles(principal, "admin", "marketer", "reviewer")


def _invitation_response(
    grant: GuestGrant,
    invitation_secret: str,
    settings: Settings,
) -> dict[str, Any]:
    return {
        "id": str(grant.id),
        "campaign_id": str(grant.campaign_id),
        "creator_id": str(grant.creator_id),
        "submission_id": str(grant.submission_id),
        "allowed_actions": _ordered_guest_actions(grant.allowed_actions),
        "expires_at": as_utc(grant.expires_at),
        "invitation_url": f"{settings.guest_public_origin}/creator#invite={invitation_secret}",
    }


def _guest_grant_family(session: Session, root_id: UUID) -> list[GuestGrant]:
    return list(
        session.scalars(
            select(GuestGrant)
            .where(GuestGrant.renewal_root_id == root_id)
            .order_by(GuestGrant.created_at, GuestGrant.id)
            .with_for_update()
        ).all()
    )


def _rotate_guest_grant_family(
    session: Session,
    principal: Principal,
    family: list[GuestGrant],
    *,
    reason: str,
) -> tuple[GuestGrant, str]:
    if not family:
        raise not_found()
    latest = family[-1]
    root_id = latest.renewal_root_id
    now = datetime.now(UTC)
    family_ids = [grant.id for grant in family]
    for grant in family:
        if grant.revoked_at is None:
            grant.revoked_at = now
    session.execute(
        update(GuestSession)
        .where(
            GuestSession.grant_id.in_(family_ids),
            GuestSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    invitation_secret = secrets.token_urlsafe(32)
    renewed = GuestGrant(
        id=uuid4(),
        organization_id=latest.organization_id,
        campaign_id=latest.campaign_id,
        creator_id=latest.creator_id,
        submission_id=latest.submission_id,
        issued_by_user_id=latest.issued_by_user_id,
        issuance_recovery_id=latest.issuance_recovery_id,
        renewal_root_id=root_id,
        scope_kind=latest.scope_kind,
        invitation_secret_hash=hashlib.sha256(
            invitation_secret.encode("utf-8")
        ).hexdigest(),
        allowed_actions=list(latest.allowed_actions),
        expires_at=now + INVITATION_LIFETIME,
        source_count=max(grant.source_count for grant in family),
        reserved_bytes=max(grant.reserved_bytes for grant in family),
    )
    session.add(renewed)
    session.flush()
    audit(
        session,
        principal,
        "guest_grant.renewed",
        "guest_grant",
        renewed.id,
        {"renewal_root_id": str(root_id), "reason": reason},
    )
    return renewed, invitation_secret


def issue_guest_invitation(
    session: Session,
    principal: Principal,
    settings: Settings,
    campaign_id: UUID,
    payload: GuestInvitationCreate,
) -> dict[str, Any]:
    _require_guest_runtime(settings)
    _require_grant_issuer_role(
        principal,
        "created_submission" if payload.submission_id is None else "existing_submission",
    )
    lock_lineage(session, principal.organization_id)
    campaign = get_campaign(session, principal, campaign_id)
    rostered = session.scalar(
        select(CampaignCreator.id).where(
            CampaignCreator.organization_id == principal.organization_id,
            CampaignCreator.campaign_id == campaign.id,
            CampaignCreator.creator_id == payload.creator_id,
        )
    )
    if rostered is None:
        raise not_found()
    existing_family = list(
        session.scalars(
            select(GuestGrant)
            .where(
                GuestGrant.organization_id == principal.organization_id,
                GuestGrant.issued_by_user_id == principal.user_id,
                GuestGrant.issuance_recovery_id == payload.recovery_id,
            )
            .order_by(GuestGrant.created_at, GuestGrant.id)
            .with_for_update()
        ).all()
    )
    if existing_family:
        existing = existing_family[0]
        expected_scope = (
            payload.submission_id is None and existing.scope_kind == "created_submission"
        ) or (
            payload.submission_id is not None
            and existing.scope_kind == "existing_submission"
            and existing.submission_id == payload.submission_id
        )
        if (
            existing.campaign_id != campaign.id
            or existing.creator_id != payload.creator_id
            or not expected_scope
        ):
            raise conflict(
                "GUEST_RECOVERY_SCOPE_MISMATCH",
                "That recovery identifier is already bound to another invitation scope.",
            )
        submission_exists = session.scalar(
            select(Submission.id).where(
                Submission.organization_id == principal.organization_id,
                Submission.id == existing.submission_id,
                Submission.campaign_id == campaign.id,
                Submission.creator_id == payload.creator_id,
                Submission.deleted_at.is_(None),
            )
        )
        if submission_exists is None:
            raise not_found()
        renewed, invitation_secret = _rotate_guest_grant_family(
            session,
            principal,
            existing_family,
            reason="issuance_recovery",
        )
        session.commit()
        return _invitation_response(renewed, invitation_secret, settings)
    submission: Submission
    if payload.submission_id is None:
        submission = Submission(
            organization_id=principal.organization_id,
            campaign_id=campaign.id,
            creator_id=payload.creator_id,
        )
        session.add(submission)
        session.flush()
        scope_kind = "created_submission"
        audit(
            session,
            principal,
            "submission.creator_placeholder_created",
            "submission",
            submission.id,
        )
    else:
        existing_submission = session.scalar(
            select(Submission)
            .where(
                Submission.organization_id == principal.organization_id,
                Submission.id == payload.submission_id,
                Submission.campaign_id == campaign.id,
                Submission.creator_id == payload.creator_id,
                Submission.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if existing_submission is None:
            raise not_found()
        submission = existing_submission
        scope_kind = "existing_submission"

    invitation_secret = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    grant_id = uuid4()
    grant = GuestGrant(
        id=grant_id,
        organization_id=principal.organization_id,
        campaign_id=campaign.id,
        creator_id=payload.creator_id,
        submission_id=submission.id,
        issued_by_user_id=principal.user_id,
        issuance_recovery_id=payload.recovery_id,
        renewal_root_id=grant_id,
        scope_kind=scope_kind,
        invitation_secret_hash=hashlib.sha256(invitation_secret.encode("utf-8")).hexdigest(),
        allowed_actions=list(MUTATION_ACTIONS),
        expires_at=now + INVITATION_LIFETIME,
    )
    session.add(grant)
    session.flush()
    audit(
        session,
        principal,
        "guest_grant.issued",
        "guest_grant",
        grant.id,
        {"scope_kind": scope_kind, "allowed_actions": MUTATION_ACTIONS},
    )
    session.commit()
    return _invitation_response(grant, invitation_secret, settings)


def revoke_guest_invitation(
    session: Session,
    principal: Principal,
    settings: Settings,
    grant_id: UUID,
) -> dict[str, str]:
    _require_guest_runtime(settings)
    lock_lineage(session, principal.organization_id)
    grant = session.scalar(
        select(GuestGrant)
        .where(
            GuestGrant.id == grant_id,
            GuestGrant.organization_id == principal.organization_id,
        )
        .with_for_update()
    )
    if grant is None:
        raise not_found()
    _require_grant_issuer_role(principal, grant.scope_kind)
    family = _guest_grant_family(session, grant.renewal_root_id)
    now = datetime.now(UTC)
    changed = False
    for family_grant in family:
        if family_grant.revoked_at is None:
            family_grant.revoked_at = now
            changed = True
    if changed:
        session.execute(
            update(GuestSession)
            .where(
                GuestSession.grant_id.in_([item.id for item in family]),
                GuestSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        audit(
            session,
            principal,
            "guest_grant.revoked",
            "guest_grant",
            grant.id,
            {"renewal_root_id": str(grant.renewal_root_id)},
        )
    session.commit()
    return {"status": "revoked"}


def renew_guest_invitation(
    session: Session,
    principal: Principal,
    settings: Settings,
    grant_id: UUID,
) -> dict[str, Any]:
    _require_guest_runtime(settings)
    lock_lineage(session, principal.organization_id)
    grant = session.scalar(
        select(GuestGrant)
        .where(
            GuestGrant.id == grant_id,
            GuestGrant.organization_id == principal.organization_id,
        )
        .with_for_update()
    )
    if grant is None:
        raise not_found()
    _require_grant_issuer_role(principal, grant.scope_kind)
    if grant.issued_by_user_id != principal.user_id:
        raise forbidden(
            "GUEST_RENEWAL_ISSUER_MISMATCH",
            "Only the member who issued this invitation can renew its credential.",
        )
    get_campaign(session, principal, grant.campaign_id)
    rostered = session.scalar(
        select(CampaignCreator.id).where(
            CampaignCreator.organization_id == principal.organization_id,
            CampaignCreator.campaign_id == grant.campaign_id,
            CampaignCreator.creator_id == grant.creator_id,
        )
    )
    submission_exists = session.scalar(
        select(Submission.id).where(
            Submission.organization_id == principal.organization_id,
            Submission.id == grant.submission_id,
            Submission.campaign_id == grant.campaign_id,
            Submission.creator_id == grant.creator_id,
            Submission.deleted_at.is_(None),
        )
    )
    if rostered is None or submission_exists is None:
        raise not_found()
    family = _guest_grant_family(session, grant.renewal_root_id)
    renewed, invitation_secret = _rotate_guest_grant_family(
        session,
        principal,
        family,
        reason="explicit_renewal",
    )
    session.commit()
    return _invitation_response(renewed, invitation_secret, settings)


def _record_exchange_attempt(
    session: Session,
    client_bucket_hash: str,
    token_digest: str,
    now: datetime,
) -> bool:
    window_start = now - EXCHANGE_WINDOW
    client_attempts = session.scalar(
        select(func.count())
        .select_from(GuestExchangeAttempt)
        .where(
            GuestExchangeAttempt.client_bucket_hash == client_bucket_hash,
            GuestExchangeAttempt.attempted_at >= window_start,
        )
    )
    token_attempts = session.scalar(
        select(func.count())
        .select_from(GuestExchangeAttempt)
        .where(
            GuestExchangeAttempt.token_digest == token_digest,
            GuestExchangeAttempt.attempted_at >= window_start,
        )
    )
    within_limits = (client_attempts or 0) < CLIENT_ATTEMPT_LIMIT and (
        token_attempts or 0
    ) < TOKEN_ATTEMPT_LIMIT
    if within_limits:
        session.add(
            GuestExchangeAttempt(
                client_bucket_hash=client_bucket_hash,
                token_digest=token_digest,
                attempted_at=now,
            )
        )
    return within_limits


def exchange_guest_invitation(
    session: Session,
    settings: Settings,
    invitation_secret: str,
    client_bucket_hash: str,
) -> tuple[str, datetime]:
    _require_guest_runtime(settings)
    now = datetime.now(UTC)
    token_digest = hashlib.sha256(invitation_secret.encode("utf-8")).hexdigest()
    if settings.auth_mode == "supabase":
        session_secret = secrets.token_urlsafe(32)
        session_id = uuid4()
        row = session.execute(
            text(
                "select * from vouch_private.exchange_guest_invitation("
                ":token_digest, :client_bucket, :session_id, :session_digest)"
            ),
            {
                "token_digest": token_digest,
                "client_bucket": client_bucket_hash,
                "session_id": session_id,
                "session_digest": hashlib.sha256(
                    session_secret.encode("utf-8")
                ).hexdigest(),
            },
        ).mappings().one_or_none()
        session.commit()
        if row is None:
            raise guest_access_ended()
        return session_secret, as_utc(row["session_expires_at"])
    within_limits = _record_exchange_attempt(session, client_bucket_hash, token_digest, now)
    if not within_limits:
        session.commit()
        raise guest_access_ended()
    probe = session.scalar(
        select(GuestGrant).where(GuestGrant.invitation_secret_hash == token_digest)
    )
    if probe is None:
        session.commit()
        raise guest_access_ended()
    lock_lineage(session, probe.organization_id)
    grant = session.scalar(
        select(GuestGrant)
        .where(
            GuestGrant.id == probe.id,
            GuestGrant.invitation_secret_hash == token_digest,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if grant is None or not guest_grant_is_authorized(
        session, grant, now, require_consumed=False
    ):
        session.commit()
        raise guest_access_ended()
    session_secret = secrets.token_urlsafe(32)
    expires_at = min(now + SESSION_LIFETIME, as_utc(grant.expires_at))
    guest_session = GuestSession(
        id=uuid4(),
        organization_id=grant.organization_id,
        grant_id=grant.id,
        session_secret_hash=hashlib.sha256(session_secret.encode("utf-8")).hexdigest(),
        expires_at=expires_at,
    )
    grant.consumed_at = now
    session.add(guest_session)
    session.commit()
    return session_secret, expires_at


def guest_submission_context(
    session: Session,
    principal: GuestPrincipal,
) -> dict[str, Any]:
    if READ_ACTION not in principal.allowed_actions:
        raise guest_access_ended()
    if principal.database_function_backed:
        result = session.scalar(text("select vouch_private.guest_submission_context()"))
        if not isinstance(result, dict):
            raise guest_access_ended()
        source_context = session.scalar(
            text("select vouch_private.guest_current_source_context()")
        )
        current_version = result.get("submission", {}).get("current_version")
        if isinstance(current_version, dict) and isinstance(source_context, dict):
            current_version["id"] = source_context.get("version_id")
            current_version["consent_receipt_id"] = source_context.get("receipt_id")
        return result
    campaign = session.scalar(
        select(Campaign).where(
            Campaign.id == principal.campaign_id,
            Campaign.organization_id == principal.organization_id,
        )
    )
    creator = session.scalar(
        select(Creator).where(
            Creator.id == principal.creator_id,
            Creator.organization_id == principal.organization_id,
        )
    )
    submission = session.scalar(
        select(Submission).where(
            Submission.id == principal.submission_id,
            Submission.organization_id == principal.organization_id,
            Submission.campaign_id == principal.campaign_id,
            Submission.creator_id == principal.creator_id,
            Submission.deleted_at.is_(None),
        )
    )
    if campaign is None or creator is None or submission is None:
        raise guest_access_ended()
    product = session.scalar(
        select(Product).where(
            Product.id == campaign.product_id,
            Product.organization_id == principal.organization_id,
        )
    )
    brand = (
        session.scalar(
            select(Brand).where(
                Brand.id == product.brand_id,
                Brand.organization_id == principal.organization_id,
            )
        )
        if product is not None
        else None
    )
    if product is None or brand is None:
        raise guest_access_ended()

    current_version = None
    review_state = "awaiting_brand_review"
    approved_version_no = None
    if submission.current_version_id is not None:
        checked_at = datetime.now(UTC)
        version = session.scalar(
            select(SubmissionVersion).where(
                SubmissionVersion.id == submission.current_version_id,
                SubmissionVersion.submission_id == submission.id,
                SubmissionVersion.organization_id == principal.organization_id,
            )
        )
        if version is None:
            raise guest_access_ended()
        source = session.scalar(
            select(MediaAsset).where(
                MediaAsset.id == version.asset_id,
                MediaAsset.organization_id == principal.organization_id,
                MediaAsset.deleted_at.is_(None),
                MediaAsset.retention_deadline > checked_at,
            )
        )
        source_denied = session.scalar(
            select(Tombstone.id).where(
                Tombstone.organization_id == principal.organization_id,
                Tombstone.resource_type == "media_asset",
                Tombstone.resource_id == version.asset_id,
            )
        )
        if source is None or source_denied is not None:
            raise guest_access_ended()
        contexts = session.scalars(
            select(ReviewContext).where(
                ReviewContext.organization_id == principal.organization_id,
                ReviewContext.submission_id == submission.id,
                ReviewContext.submission_version_id == version.id,
                ReviewContext.review_status != "superseded",
            )
        ).all()
        approved_context = next(
            (context for context in contexts if context.review_status == "approved"), None
        )
        if approved_context is not None:
            approval = session.scalar(
                select(Approval.id).where(
                    Approval.organization_id == principal.organization_id,
                    Approval.review_context_id == approved_context.id,
                    Approval.submission_version_id == version.id,
                )
            )
            if approval is not None:
                review_state = "approved"
                approved_version_no = version.version_no
        elif any(context.review_status == "changes_requested" for context in contexts):
            review_state = "changes_requested"
        receipt_id = session.scalar(
            select(ConsentReceipt.id).where(
                ConsentReceipt.organization_id == principal.organization_id,
                ConsentReceipt.asset_id == version.asset_id,
            )
        )
        current_version = {
            "id": str(version.id),
            "version_no": version.version_no,
            "caption": version.caption,
            "created_at": as_utc(version.created_at),
            "consent_receipt_id": str(receipt_id) if receipt_id else None,
        }
    feedback_rows = session.execute(
        select(CreatorFeedback, SubmissionVersion.version_no)
        .join(
            SubmissionVersion,
            and_(
                SubmissionVersion.id == CreatorFeedback.submission_version_id,
                SubmissionVersion.organization_id == CreatorFeedback.organization_id,
                SubmissionVersion.submission_id == CreatorFeedback.submission_id,
            ),
        )
        .where(
            CreatorFeedback.organization_id == principal.organization_id,
            CreatorFeedback.submission_id == submission.id,
            CreatorFeedback.message != "",
        )
        .order_by(CreatorFeedback.published_at, CreatorFeedback.id)
    ).all()
    return {
        "session_expires_at": as_utc(principal.session_expires_at),
        "campaign": {
            "name": campaign.name,
            "market": campaign.market,
            "brand_name": brand.name,
        },
        "creator": {"name": creator.name, "handle": creator.handle},
        "submission": {
            "current_version": current_version,
            "review_state": review_state,
            "approved_version_no": approved_version_no,
        },
        "allowed_actions": _ordered_guest_actions(principal.allowed_actions),
        "feedback": [
            {
                "version_no": version_no,
                "message": feedback.message,
                "start_ms": feedback.start_ms,
                "end_ms": feedback.end_ms,
                "invocation_mode": feedback.invocation_mode,
                "analysis_status": feedback.analysis_status,
                "manifest_hash": feedback.manifest_hash,
                "published_at": as_utc(feedback.published_at),
                "historical": submission.current_version_id != feedback.submission_version_id,
            }
            for feedback, version_no in feedback_rows
        ],
    }


def withdraw_guest_source(
    session: Session,
    principal: GuestPrincipal,
    receipt_id: UUID,
) -> dict[str, Any]:
    """Withdraw only an exact source created by this invitation's renewal family."""
    if principal.database_function_backed:
        result = session.scalar(
            text("select vouch_private.guest_withdraw_source(:receipt_id)"),
            {"receipt_id": receipt_id},
        )
        if not isinstance(result, dict):
            raise guest_access_ended()
        session.commit()
        return result

    lock_lineage(session, principal.organization_id)
    grant, _guest_session, submission = _current_guest_scope(
        session, principal, READ_ACTION, lock_submission=True
    )
    receipt = session.scalar(
        select(ConsentReceipt).where(
            ConsentReceipt.id == receipt_id,
            ConsentReceipt.organization_id == principal.organization_id,
            ConsentReceipt.campaign_id == principal.campaign_id,
            ConsentReceipt.actor_guest_session_id.is_not(None),
        )
    )
    if receipt is None:
        raise not_found()
    asset = session.scalar(
        select(MediaAsset).where(
            MediaAsset.id == receipt.asset_id,
            MediaAsset.organization_id == principal.organization_id,
            MediaAsset.campaign_id == principal.campaign_id,
            MediaAsset.uploader_guest_session_id == receipt.actor_guest_session_id,
        )
    )
    attached = session.scalar(
        select(SubmissionVersion.id).where(
            SubmissionVersion.organization_id == principal.organization_id,
            SubmissionVersion.submission_id == submission.id,
            SubmissionVersion.asset_id == receipt.asset_id,
        )
    )
    source_session = (
        session.get(GuestSession, asset.uploader_guest_session_id)
        if asset is not None and asset.uploader_guest_session_id is not None
        else None
    )
    source_grant = (
        session.get(GuestGrant, source_session.grant_id) if source_session is not None else None
    )
    grant_root = grant.renewal_root_id or grant.id
    source_root = (
        source_grant.renewal_root_id or source_grant.id if source_grant is not None else None
    )
    if asset is None or attached is None or source_root != grant_root:
        raise not_found()
    deletion = _erase_source(
        session,
        principal,
        DeletionRequestCreate(resource_type="media_asset", resource_id=asset.id),
        revocation_reason="withdrawn",
    )
    return deletion_dict(deletion)


def _require_guest_mutation_runtime(settings: Settings) -> None:
    _require_guest_runtime(settings)
    if settings.auth_mode == "supabase" and settings.guest_storage_key is None:
        raise ApiError(
            503,
            "GUEST_STORAGE_UNAVAILABLE",
            "Creator media upload is not configured for this environment.",
            True,
        )


def _guest_receipt_dict(receipt: ConsentReceipt) -> dict[str, Any]:
    return {
        "id": str(receipt.id),
        "purpose": receipt.purpose,
        "notice_version": receipt.notice_version,
        "notice_hash": receipt.notice_hash,
        "accepted_at": as_utc(receipt.accepted_at),
    }


def _assert_guest_upload_unexpired(asset: MediaAsset) -> None:
    if datetime.now(UTC) >= as_utc(asset.created_at) + UPLOAD_LIFETIME:
        raise ApiError(
            401,
            "UPLOAD_AUTHORIZATION_EXPIRED",
            "Create a new creator upload authorization.",
        )


def _guest_asset(
    session: Session,
    principal: GuestPrincipal,
    asset_id: UUID,
    *,
    require_upload_window: bool,
) -> tuple[MediaAsset, ConsentReceipt]:
    asset_query = select(MediaAsset).where(
        MediaAsset.id == asset_id,
        MediaAsset.organization_id == principal.organization_id,
        MediaAsset.campaign_id == principal.campaign_id,
        MediaAsset.uploader_user_id.is_(None),
        MediaAsset.uploader_guest_session_id == principal.session_id,
    )
    if _uses_guest_runtime_role(session):
        locked = session.scalar(
            text("select vouch_private.lock_guest_source(:asset_id)"),
            {"asset_id": asset_id},
        )
        if locked is not True:
            raise not_found()
    else:
        asset_query = asset_query.with_for_update()
    asset = session.scalar(asset_query.execution_options(populate_existing=True))
    if asset is None or asset.deleted_at is not None or asset.status == "deleted":
        raise not_found()
    if require_upload_window:
        _assert_guest_upload_unexpired(asset)
    if source_expired(asset):
        raise conflict("RESOURCE_EXPIRED", "The source retention deadline has passed.")
    if session.scalar(
        select(Tombstone.id).where(
            Tombstone.organization_id == principal.organization_id,
            Tombstone.resource_type == "media_asset",
            Tombstone.resource_id == asset.id,
        )
    ):
        raise not_found()
    receipt = session.scalar(
        select(ConsentReceipt).where(
            ConsentReceipt.organization_id == principal.organization_id,
            ConsentReceipt.asset_id == asset.id,
            ConsentReceipt.campaign_id == principal.campaign_id,
            ConsentReceipt.actor_user_id.is_(None),
            ConsentReceipt.actor_guest_session_id == principal.session_id,
        )
    )
    if receipt is None or not source_authorization_active(
        session, asset, principal.organization_id
    ):
        raise conflict(
            "PROCESSING_AUTHORIZATION_REQUIRED",
            "A fresh creator upload with active notice acknowledgment is required.",
        )
    return asset, receipt


def _guest_intent_response(
    asset: MediaAsset,
    receipt: ConsentReceipt,
    settings: Settings,
) -> dict[str, Any]:
    if asset.uploader_guest_session_id is None:
        raise not_found()
    upload_token = _capability_token(
        settings, "upload", asset.id, asset.uploader_guest_session_id
    )
    finalize_token = _capability_token(
        settings, "finalize", asset.id, asset.uploader_guest_session_id
    )
    return {
        "upload_id": str(asset.id),
        "content_url": f"/api/v1/guest/uploads/{asset.id}/content",
        "upload_token": upload_token,
        "finalize_url": f"/api/v1/guest/uploads/{asset.id}/finalize",
        "finalize_token": finalize_token,
        "required_header": "X-Upload-Token",
        "max_bytes": MAX_MEDIA_BYTES,
        "expires_at": as_utc(asset.created_at) + UPLOAD_LIFETIME,
        "authorization_status": "active",
        "consent_receipt": _guest_receipt_dict(receipt),
    }


def _guest_workspace_available_bytes(
    session: Session,
    principal: GuestPrincipal,
    settings: Settings,
) -> int:
    if settings.auth_mode == "supabase" and session.get_bind().dialect.name == "postgresql":
        value = session.scalar(text("select vouch_private.guest_workspace_storage_available()"))
        if not isinstance(value, int):
            raise ApiError(
                503,
                "GUEST_STORAGE_UNAVAILABLE",
                "Creator media upload is not configured for this environment.",
                True,
            )
        return value
    return workspace_storage_usage_for(
        session,
        principal.organization_id,
        "supabase" if settings.auth_mode == "supabase" else "database",
    ).available_bytes


def create_guest_upload_intent(
    session: Session,
    principal: GuestPrincipal,
    settings: Settings,
    payload: GuestUploadIntentCreate,
    idempotency_key: str | None,
) -> dict[str, Any]:
    _require_guest_mutation_runtime(settings)
    require_guest_action(principal, UPLOAD_ACTION)
    key = _idempotency_key(idempotency_key)
    notice = require_current_guest_notice(payload.notice_version)
    request_digest = stable_hash(payload.model_dump(mode="json"))
    lock_lineage(session, principal.organization_id)
    grant, _guest_session, _submission = _current_guest_scope(
        session, principal, UPLOAD_ACTION, lock_submission=True
    )
    command = _guest_command(session, principal, UPLOAD_OPERATION, key)
    if command is not None:
        _assert_command_digest(command, request_digest)
        if command.result_resource_type != "media_asset":
            raise conflict(
                "GUEST_COMMAND_RESULT_UNAVAILABLE",
                "The prior creator upload result is unavailable.",
            )
        asset, receipt = _guest_asset(
            session,
            principal,
            command.result_resource_id,
            require_upload_window=True,
        )
        return _guest_intent_response(asset, receipt, settings)
    if _guest_workspace_available_bytes(session, principal, settings) < MAX_MEDIA_BYTES:
        raise conflict(
            "STORAGE_ALLOWANCE_EXCEEDED",
            "Workspace storage is full. Ask the workspace owner to remove unused sources and "
            "wait for cleanup before uploading.",
        )
    reserved_grant_id = session.scalar(
        update(GuestGrant)
        .where(
            GuestGrant.id == grant.id,
            GuestGrant.organization_id == principal.organization_id,
            GuestGrant.source_count < MAX_GRANT_SOURCES,
            GuestGrant.reserved_bytes <= MAX_GRANT_BYTES - payload.byte_size,
        )
        .values(
            source_count=GuestGrant.source_count + 1,
            reserved_bytes=GuestGrant.reserved_bytes + payload.byte_size,
        )
        .returning(GuestGrant.id)
    )
    if reserved_grant_id is None:
        raise conflict(
            "GUEST_UPLOAD_QUOTA_EXCEEDED",
            "This creator invitation has reached its upload allowance. Ask the sender for help.",
        )
    asset_id = uuid4()
    upload_token = _capability_token(settings, "upload", asset_id, principal.session_id)
    finalize_token = _capability_token(settings, "finalize", asset_id, principal.session_id)
    asset = MediaAsset(
        id=asset_id,
        organization_id=principal.organization_id,
        campaign_id=principal.campaign_id,
        uploader_user_id=None,
        uploader_guest_session_id=principal.session_id,
        filename=payload.filename,
        proposed_content_type=payload.content_type,
        expected_bytes=payload.byte_size,
        upload_token_hash=sha256_text(upload_token),
        finalize_token_hash=sha256_text(finalize_token),
        rights_attested=payload.rights_attested,
        retention_deadline=datetime.now(UTC) + timedelta(days=30),
        storage_backend="supabase" if settings.auth_mode == "supabase" else "database",
        object_key=(
            f"{principal.organization_id}/{principal.campaign_id}/{asset_id}/source"
            if settings.auth_mode == "supabase"
            else None
        ),
    )
    session.add(asset)
    session.flush()
    receipt = ConsentReceipt(
        organization_id=principal.organization_id,
        asset_id=asset.id,
        campaign_id=principal.campaign_id,
        actor_user_id=None,
        actor_guest_session_id=principal.session_id,
        purpose=payload.purpose,
        notice_version=notice.version,
        notice_hash=notice.notice_hash,
    )
    session.add(receipt)
    session.flush()
    session.add(
        GuestCommand(
            organization_id=principal.organization_id,
            guest_session_id=principal.session_id,
            operation=UPLOAD_OPERATION,
            idempotency_key=key,
            request_digest=request_digest,
            result_resource_type="media_asset",
            result_resource_id=asset.id,
        )
    )
    audit(
        session,
        None,
        "processing.authorization_acknowledged",
        "consent_receipt",
        receipt.id,
        organization_id=principal.organization_id,
        actor_guest_session_id=principal.session_id,
    )
    audit(
        session,
        None,
        "guest_upload.intent_created",
        "media_asset",
        asset.id,
        {"expected_bytes": asset.expected_bytes},
        organization_id=principal.organization_id,
        actor_guest_session_id=principal.session_id,
    )
    session.commit()
    return _guest_intent_response(asset, receipt, settings)


def put_guest_upload_content(
    session: Session,
    principal: GuestPrincipal,
    settings: Settings,
    upload_id: UUID,
    upload_token: str | None,
    content_type: str | None,
    body: bytes,
) -> dict[str, Any]:
    _require_guest_mutation_runtime(settings)
    lock_lineage(session, principal.organization_id)
    _current_guest_scope(session, principal, UPLOAD_ACTION, lock_submission=True)
    asset, _receipt = _guest_asset(
        session, principal, upload_id, require_upload_window=True
    )
    if not upload_token or not secrets.compare_digest(
        asset.upload_token_hash, sha256_text(upload_token)
    ):
        raise ApiError(401, "UPLOAD_TOKEN_INVALID", "The upload token is invalid or expired.")
    normalized_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if normalized_type != asset.proposed_content_type:
        raise ApiError(
            415,
            "UNSUPPORTED_MEDIA_TYPE",
            "Content-Type does not match the upload intent.",
        )
    if len(body) != asset.expected_bytes:
        raise unprocessable(
            "UPLOAD_SIZE_MISMATCH",
            "The received byte length does not match the declared upload size.",
        )
    content_hash = sha256_bytes(body)
    if asset.status == "validated":
        # The browser may have lost the finalize response and replay the same
        # command chain. Acknowledge only the exact immutable source bytes;
        # never write to Storage or reopen the validated asset.
        if asset.actual_bytes != len(body) or asset.sha256 != content_hash:
            raise conflict(
                "UPLOAD_CONTENT_CONFLICT",
                "This upload was finalized with different bytes.",
            )
        return {
            "upload_id": str(asset.id),
            "status": "content_uploaded",
            "received_bytes": len(body),
        }
    if asset.status not in {"intent_created", "content_uploaded"}:
        raise conflict(
            "UPLOAD_STATE_CONFLICT",
            "This upload cannot accept content in its current state.",
        )
    if asset.storage_backend == "supabase":
        if not asset.object_key:
            raise not_found()
        store = session.info.get("guest_media_store")
        if store is None:
            raise ApiError(
                503,
                "GUEST_STORAGE_UNAVAILABLE",
                "Creator media upload is not configured for this environment.",
                True,
            )
        object_key = asset.object_key
        # Keep the tenant-lineage and exact-source locks through this bounded
        # private Storage write. If deletion won after the commit and before a
        # late upload, its receipt could say cleanup completed while the object
        # appeared afterward. A failed/ambiguous write rolls this transaction
        # back; the same exact-key retry reconciles identical remote bytes.
        guest_store: GuestMediaStore = store
        guest_store.upload(object_key, body, normalized_type)
        lock_lineage(session, principal.organization_id)
        _current_guest_scope(session, principal, UPLOAD_ACTION, lock_submission=True)
        asset, _receipt = _guest_asset(
            session, principal, upload_id, require_upload_window=True
        )
        if asset.object_key != object_key:
            raise conflict(
                "UPLOAD_CONTENT_CONFLICT",
                "The authorized upload changed while content was stored.",
            )
        asset.object_bytes = None
    elif asset.status == "content_uploaded":
        if asset.object_bytes != body:
            raise conflict(
                "UPLOAD_CONTENT_CONFLICT",
                "This upload already has different bytes.",
            )
    else:
        asset.object_bytes = body
    if asset.status == "content_uploaded":
        if asset.sha256 != content_hash or asset.actual_bytes != len(body):
            raise conflict(
                "UPLOAD_CONTENT_CONFLICT",
                "This upload already has different bytes.",
            )
        return {
            "upload_id": str(asset.id),
            "status": "content_uploaded",
            "received_bytes": len(body),
        }
    asset.actual_bytes = len(body)
    asset.sha256 = content_hash
    asset.status = "content_uploaded"
    session.commit()
    return {
        "upload_id": str(asset.id),
        "status": "content_uploaded",
        "received_bytes": len(body),
    }


def finalize_guest_upload(
    session: Session,
    principal: GuestPrincipal,
    settings: Settings,
    upload_id: UUID,
    finalize_token: str,
) -> dict[str, Any]:
    _require_guest_mutation_runtime(settings)
    lock_lineage(session, principal.organization_id)
    _current_guest_scope(session, principal, UPLOAD_ACTION, lock_submission=True)
    asset, _receipt = _guest_asset(
        session, principal, upload_id, require_upload_window=True
    )
    if not secrets.compare_digest(
        asset.finalize_token_hash, sha256_text(finalize_token)
    ):
        raise ApiError(401, "FINALIZE_TOKEN_INVALID", "The finalization token is invalid.")
    if asset.status == "validated":
        return {"asset_id": str(asset.id), "status": "validated"}
    if asset.status != "content_uploaded":
        raise conflict("UPLOAD_NOT_READY", "Upload content must be received before finalization.")
    processor: MediaProcessor = session.info["media_processor"]
    if asset.processing_container:
        if (
            asset.processing_lease_until
            and as_utc(asset.processing_lease_until) > datetime.now(UTC)
        ):
            raise conflict(
                "MEDIA_PROCESSING_IN_PROGRESS",
                "Media validation is already in progress.",
            )
        remove_sandbox_container(asset.processing_container, principal.organization_id)
    prepared = processor.prepare(
        asset.proposed_content_type, principal.organization_id, asset.id
    )
    if prepared is not None:
        asset.processing_container = prepared.name
        asset.processing_lease_until = datetime.now(UTC) + timedelta(seconds=60)
    snapshot = {
        "sha256": asset.sha256,
        "expected_bytes": asset.expected_bytes,
        "actual_bytes": asset.actual_bytes,
        "proposed_content_type": asset.proposed_content_type,
        "storage_backend": asset.storage_backend,
        "object_key": asset.object_key,
        "processing_container": asset.processing_container,
    }
    body = asset.object_bytes
    session.commit()
    try:
        if snapshot["storage_backend"] == "supabase":
            object_key = snapshot["object_key"]
            store = session.info.get("guest_media_store")
            if not isinstance(object_key, str) or store is None:
                raise ApiError(
                    503,
                    "GUEST_STORAGE_UNAVAILABLE",
                    "Creator media upload is not configured for this environment.",
                    True,
                )
            guest_store: GuestMediaStore = store
            body = guest_store.download(object_key)
        body, detected, processed = _validate_staged_media(
            body, snapshot, processor, prepared
        )
    finally:
        if prepared is not None:
            remove_sandbox_container(prepared.name, principal.organization_id)
    original_hash = sha256_bytes(body)
    metadata = processed.model_dump(mode="json")
    lock_lineage(session, principal.organization_id)
    _current_guest_scope(session, principal, UPLOAD_ACTION, lock_submission=True)
    asset, _receipt = _guest_asset(
        session, principal, upload_id, require_upload_window=True
    )
    if any(
        getattr(asset, field) != value
        for field, value in snapshot.items()
        if field != "sha256"
    ):
        raise conflict(
            "UPLOAD_CONTENT_CONFLICT",
            "The authorized upload changed during processing.",
        )
    if asset.status == "validated":
        if asset.sha256 == original_hash and asset.processing_metadata == metadata:
            return {"asset_id": str(asset.id), "status": "validated"}
        raise conflict(
            "UPLOAD_STATE_CONFLICT",
            "The asset was finalized with different metadata.",
        )
    if asset.sha256 != snapshot["sha256"]:
        raise conflict(
            "UPLOAD_CONTENT_CONFLICT",
            "The authorized upload changed during processing.",
        )
    if asset.status != "content_uploaded":
        raise conflict(
            "UPLOAD_NOT_READY",
            "The upload is no longer available for finalization.",
        )
    if asset.storage_backend == "database" and asset.object_bytes != body:
        raise conflict(
            "UPLOAD_CONTENT_CONFLICT",
            "Stored media changed during processing.",
        )
    asset.validated_content_type = detected
    asset.sha256 = original_hash
    asset.duration_ms = processed.duration_ms
    asset.processing_metadata = metadata
    asset.status = "validated"
    audit(
        session,
        None,
        "guest_upload.validated",
        "media_asset",
        asset.id,
        {
            "bytes": asset.actual_bytes,
            "validated_content_type": detected,
            "media_mode": processed.mode,
            "processor_version": processed.processor_version,
        },
        organization_id=principal.organization_id,
        actor_guest_session_id=principal.session_id,
    )
    session.commit()
    return {"asset_id": str(asset.id), "status": "validated"}


def _guest_version_response(version: SubmissionVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "version_no": version.version_no,
        "caption": version.caption,
        "created_at": as_utc(version.created_at),
    }


def create_guest_submission_version(
    session: Session,
    principal: GuestPrincipal,
    payload: GuestSubmissionVersionCreate,
    idempotency_key: str | None,
) -> dict[str, Any]:
    require_guest_action(principal, SUBMIT_ACTION)
    key = _idempotency_key(idempotency_key)
    request_digest = stable_hash(payload.model_dump(mode="json"))
    lock_lineage(session, principal.organization_id)
    _grant, _guest_session, submission = _current_guest_scope(
        session, principal, SUBMIT_ACTION, lock_submission=True
    )
    command = _guest_command(session, principal, VERSION_OPERATION, key)
    if command is not None:
        _assert_command_digest(command, request_digest)
        if command.result_resource_type != "submission_version":
            raise conflict(
                "GUEST_COMMAND_RESULT_UNAVAILABLE",
                "The prior creator submission result is unavailable.",
            )
        version = session.scalar(
            select(SubmissionVersion).where(
                SubmissionVersion.id == command.result_resource_id,
                SubmissionVersion.organization_id == principal.organization_id,
                SubmissionVersion.submission_id == principal.submission_id,
                SubmissionVersion.uploader_user_id.is_(None),
                SubmissionVersion.uploader_guest_session_id == principal.session_id,
            )
        )
        if version is None:
            raise conflict(
                "GUEST_COMMAND_RESULT_UNAVAILABLE",
                "The prior creator submission result is unavailable.",
            )
        return _guest_version_response(version)
    current_version = (
        session.scalar(
            select(SubmissionVersion).where(
                SubmissionVersion.organization_id == principal.organization_id,
                SubmissionVersion.submission_id == principal.submission_id,
                SubmissionVersion.id == submission.current_version_id,
            )
        )
        if submission.current_version_id is not None
        else None
    )
    if submission.current_version_id != payload.expected_current_version_id:
        raise conflict(
            "SUBMISSION_VERSION_CONFLICT",
            "The assigned submission changed. Reload it before submitting.",
        )
    if submission.current_version_id is not None and current_version is None:
        raise conflict(
            "SUBMISSION_VERSION_CONFLICT",
            "The current submission version is unavailable.",
        )
    if current_version is None:
        existing_version = session.scalar(
            select(SubmissionVersion.id).where(
                SubmissionVersion.organization_id == principal.organization_id,
                SubmissionVersion.submission_id == principal.submission_id,
            )
        )
        if existing_version is not None:
            raise conflict(
                "SUBMISSION_VERSION_CONFLICT",
                "The assigned submission changed. Reload it before submitting.",
            )
    next_version_no = 1 if current_version is None else current_version.version_no + 1
    asset, _receipt = _guest_asset(
        session, principal, payload.asset_id, require_upload_window=False
    )
    if asset.status != "validated" or not asset.sha256:
        raise unprocessable(
            "ASSET_NOT_VALIDATED",
            "A finalized creator upload is required before submitting.",
        )
    already_attached = session.scalar(
        select(SubmissionVersion.id).where(
            SubmissionVersion.organization_id == principal.organization_id,
            SubmissionVersion.asset_id == asset.id,
        )
    )
    if already_attached is not None:
        raise conflict(
            "ASSET_ALREADY_ATTACHED",
            "This creator upload is already attached to a submission version.",
        )
    version = SubmissionVersion(
        organization_id=principal.organization_id,
        submission_id=principal.submission_id,
        version_no=next_version_no,
        asset_id=asset.id,
        media_hash=asset.sha256,
        caption=payload.caption,
        caption_hash=sha256_text(payload.caption),
        uploader_user_id=None,
        uploader_guest_session_id=principal.session_id,
        rights_attested=True,
    )
    session.add(version)
    session.flush()
    submission.current_version_id = version.id
    session.add(
        GuestCommand(
            organization_id=principal.organization_id,
            guest_session_id=principal.session_id,
            operation=VERSION_OPERATION,
            idempotency_key=key,
            request_digest=request_digest,
            result_resource_type="submission_version",
            result_resource_id=version.id,
        )
    )
    audit(
        session,
        None,
        "guest_submission.version_created",
        "submission_version",
        version.id,
        {"version_no": next_version_no},
        organization_id=principal.organization_id,
        actor_guest_session_id=principal.session_id,
    )
    session.commit()
    return _guest_version_response(version)
