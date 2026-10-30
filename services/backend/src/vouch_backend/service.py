from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import Principal, require_roles
from .errors import (
    ApiError,
    bad_request,
    budget_exceeded,
    conflict,
    not_found,
    unprocessable,
)
from .guest_auth import GuestPrincipal
from .media import MediaProcessor, PreparedMedia, ProcessedMedia, remove_sandbox_container
from .models import (
    Analysis,
    Approval,
    AuditEvent,
    BudgetReservation,
    Campaign,
    CampaignCreator,
    CampaignRequirement,
    ConsentReceipt,
    Creator,
    CreatorEvidence,
    CreatorFeedback,
    DeletionRequest,
    EvidenceItem,
    Finding,
    FindingDecision,
    FixRequestDraft,
    IdempotencyRecord,
    Job,
    MediaAsset,
    Membership,
    MembershipRole,
    ModelCall,
    Organization,
    OutcomeEvent,
    Product,
    ProductClaim,
    ReviewContext,
    ReviewEvent,
    RulePackVersion,
    Submission,
    SubmissionVersion,
    Tombstone,
    User,
    utcnow,
)
from .notices import NOTICE_REGISTRY, require_current_notice
from .schemas import (
    CampaignCreate,
    CampaignCreatorCreate,
    CampaignRequirementCreate,
    CheckCreate,
    CreatorFeedbackCreate,
    CreatorMatchKind,
    CreatorPermissionStatus,
    CreatorVerificationStatus,
    DeletionRequestCreate,
    FindingDecisionCreate,
    FixRequestCreate,
    ProductClaimCreate,
    ReviewDecisionCreate,
    SubmissionCreate,
    SubmissionVersionCreate,
    TestOutcomeEventCreate,
    UploadIntentCreate,
)
from .storage import MAX_MEDIA_BYTES, MediaStore
from .storage_quota import workspace_storage_usage

CHECK_RESERVATION_MINOR = 25
MODEL_VERSIONS = {
    "reasoner": "fixture-spark-v1",
    "transcriber": "fixture-voice-v1",
    "segmenter": "fixture-sam-v1",
}
PROMPT_VERSION = "check-fixture-prompt.v1"


@dataclass(frozen=True, slots=True)
class RetentionActor:
    """Internal expiry authority, deliberately not an authenticated member principal."""

    organization_id: UUID
    user_id: None = None


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def stable_hash(value: object) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    )


def audit(
    session: Session,
    principal: Principal | RetentionActor | None,
    action: str,
    resource_type: str,
    resource_id: UUID,
    metadata: dict[str, Any] | None = None,
    *,
    organization_id: UUID | None = None,
    actor_guest_session_id: UUID | None = None,
) -> None:
    org_id = principal.organization_id if principal else organization_id
    if org_id is None:
        raise RuntimeError("audit event requires organization scope")
    session.add(
        AuditEvent(
            organization_id=org_id,
            actor_user_id=principal.user_id if principal else None,
            actor_guest_session_id=actor_guest_session_id,
            actor_kind=(
                "retention"
                if isinstance(principal, RetentionActor)
                else "member"
                if principal
                else "guest"
                if actor_guest_session_id is not None
                else "worker"
            ),
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            safe_metadata=metadata or {},
        )
    )


def get_campaign(session: Session, principal: Principal, campaign_id: UUID) -> Campaign:
    campaign = session.scalar(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.organization_id == principal.organization_id,
        )
    )
    if campaign is None:
        raise not_found()
    return campaign


def _outcome_event_dict(event: OutcomeEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "creator_id": str(event.creator_id),
        "event_kind": event.event_kind,
        "environment": event.environment,
        "external_event_id": event.external_event_id,
        "order_external_id": event.order_external_id,
        "amount_minor": event.amount_minor,
        "currency": event.currency,
        "attribution_status": event.attribution_status,
        "attribution_method": event.attribution_method,
        "occurred_at": _as_utc(event.occurred_at),
        "received_at": _as_utc(event.received_at),
    }


def record_test_outcome_event(
    session: Session,
    principal: Principal,
    campaign_id: UUID,
    payload: TestOutcomeEventCreate,
) -> tuple[dict[str, Any], bool]:
    require_roles(principal, "admin", "marketer")
    campaign = session.scalar(
        select(Campaign)
        .where(
            Campaign.id == campaign_id,
            Campaign.organization_id == principal.organization_id,
        )
        .with_for_update()
    )
    if campaign is None:
        raise not_found()
    rostered = session.scalar(
        select(CampaignCreator.id).where(
            CampaignCreator.organization_id == principal.organization_id,
            CampaignCreator.campaign_id == campaign.id,
            CampaignCreator.creator_id == payload.creator_id,
        )
    )
    if rostered is None:
        raise unprocessable(
            "TRACK_CREATOR_NOT_ROSTERED",
            "The creator must be on this campaign before recording a test outcome.",
        )
    payload_hash = stable_hash(payload.model_dump(mode="json"))
    existing = session.scalar(
        select(OutcomeEvent).where(
            OutcomeEvent.organization_id == principal.organization_id,
            OutcomeEvent.environment == "test",
            OutcomeEvent.external_event_id == payload.external_event_id,
        )
    )
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise conflict(
                "TRACK_EVENT_CONFLICT",
                "This external event ID was already recorded with different data.",
            )
        return _outcome_event_dict(existing), False
    if payload.event_kind in {"order", "refund"}:
        order = session.scalar(
            select(OutcomeEvent).where(
                OutcomeEvent.organization_id == principal.organization_id,
                OutcomeEvent.campaign_id == campaign.id,
                OutcomeEvent.creator_id == payload.creator_id,
                OutcomeEvent.environment == "test",
                OutcomeEvent.event_kind == "order",
                OutcomeEvent.order_external_id == payload.order_external_id,
            )
        )
        if payload.event_kind == "order" and order is not None:
            raise conflict(
                "TRACK_ORDER_CONFLICT",
                "This test order ID is already attributed to the campaign.",
            )
        if payload.event_kind == "refund":
            if order is None or order.currency != payload.currency:
                raise unprocessable(
                    "TRACK_ORDER_NOT_FOUND",
                    "A matching test order and currency are required before a refund.",
                )
            refunded = session.scalar(
                select(func.coalesce(func.sum(OutcomeEvent.amount_minor), 0)).where(
                    OutcomeEvent.organization_id == principal.organization_id,
                    OutcomeEvent.environment == "test",
                    OutcomeEvent.event_kind == "refund",
                    OutcomeEvent.order_external_id == payload.order_external_id,
                )
            )
            if int(refunded or 0) + payload.amount_minor > order.amount_minor:
                raise unprocessable(
                    "TRACK_REFUND_EXCEEDS_ORDER",
                    "Recorded refunds cannot exceed the matching test order value.",
                )
    event = OutcomeEvent(
        organization_id=principal.organization_id,
        campaign_id=campaign.id,
        creator_id=payload.creator_id,
        event_kind=payload.event_kind,
        environment="test",
        external_event_id=payload.external_event_id,
        order_external_id=payload.order_external_id,
        amount_minor=payload.amount_minor,
        currency=payload.currency,
        attribution_status="attributed",
        attribution_method="test_roster",
        payload_hash=payload_hash,
        occurred_at=payload.occurred_at,
    )
    session.add(event)
    session.flush()
    audit(
        session,
        principal,
        "track.test_event_recorded",
        "outcome_event",
        event.id,
        {"event_kind": event.event_kind, "environment": "test"},
    )
    session.commit()
    return _outcome_event_dict(event), True


def campaign_track_report(
    session: Session, principal: Principal, campaign_id: UUID
) -> dict[str, Any]:
    campaign = get_campaign(session, principal, campaign_id)
    events = session.scalars(
        select(OutcomeEvent)
        .where(
            OutcomeEvent.organization_id == principal.organization_id,
            OutcomeEvent.campaign_id == campaign.id,
        )
        .order_by(OutcomeEvent.received_at.desc(), OutcomeEvent.id.desc())
    ).all()

    def summarize(environment: str) -> dict[str, Any]:
        scoped = [event for event in events if event.environment == environment]
        clicks = sum(event.event_kind == "click" for event in scoped)
        orders = sum(event.event_kind == "order" for event in scoped)
        refunds = sum(event.event_kind == "refund" for event in scoped)
        currencies = sorted({event.currency for event in scoped if event.event_kind != "click"})
        totals: dict[str, dict[str, int]] = {}
        for currency in currencies:
            gross = sum(
                event.amount_minor
                for event in scoped
                if event.event_kind == "order" and event.currency == currency
            )
            refunded = sum(
                event.amount_minor
                for event in scoped
                if event.event_kind == "refund" and event.currency == currency
            )
            totals[currency] = {
                "gross_minor": gross,
                "refunded_minor": refunded,
                "net_minor": gross - refunded,
            }
        return {
            "clicks": clicks,
            "orders": orders,
            "refunds": refunds,
            "conversion_rate": orders / clicks if clicks else None,
            "totals_by_currency": totals,
        }

    return {
        "campaign_id": str(campaign.id),
        "freshness_at": max(
            (_as_utc(event.received_at) for event in events), default=None
        ),
        "test": summarize("test"),
        "live": summarize("live"),
        "events": [_outcome_event_dict(event) for event in events],
    }


def get_submission(
    session: Session, principal: Principal, submission_id: UUID, *, lock: bool = False
) -> Submission:
    query = select(Submission).where(
        Submission.id == submission_id,
        Submission.organization_id == principal.organization_id,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    submission = session.scalar(query)
    if submission is None:
        raise not_found()
    return submission


def get_submission_version(
    session: Session, principal: Principal, submission_version_id: UUID
) -> SubmissionVersion:
    version = session.scalar(
        select(SubmissionVersion).where(
            SubmissionVersion.id == submission_version_id,
            SubmissionVersion.organization_id == principal.organization_id,
        )
    )
    if version is None:
        raise not_found()
    return version


def get_analysis(
    session: Session, principal: Principal, analysis_id: UUID,
    *, require_authorization: bool = False,
) -> Analysis:
    analysis = session.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.organization_id == principal.organization_id,
        )
    )
    if analysis is None:
        raise not_found()
    version = get_submission_version(session, principal, analysis.submission_version_id)
    _assert_source_available(session, principal.organization_id, version)
    if require_authorization:
        asset = session.get(MediaAsset, version.asset_id)
        if asset is None:
            raise not_found()
        _require_processing_authorization(session, asset, principal.organization_id)
    return analysis


def _assert_source_available(
    session: Session, organization_id: UUID, version: SubmissionVersion
) -> Submission:
    submission = session.scalar(
        select(Submission)
        .where(
            Submission.id == version.submission_id,
            Submission.organization_id == organization_id,
        )
        .with_for_update()
    )
    asset = session.scalar(
        select(MediaAsset).where(
            MediaAsset.id == version.asset_id,
            MediaAsset.organization_id == organization_id,
        )
    )
    deleted = session.scalar(
        select(Tombstone.id).where(
            Tombstone.organization_id == organization_id,
            or_(
                (Tombstone.resource_type == "submission")
                & (Tombstone.resource_id == version.submission_id),
                (Tombstone.resource_type == "media_asset")
                & (Tombstone.resource_id == version.asset_id),
            ),
        )
    )
    if (
        submission is None
        or asset is None
        or deleted
        or submission.deleted_at is not None
        or asset.deleted_at is not None
    ):
        raise conflict("RESOURCE_DELETED", "The source and its derived review are unavailable.")
    if source_expired(asset):
        raise conflict("RESOURCE_EXPIRED", "The source retention deadline has passed.")
    return submission


def source_expired(asset: MediaAsset) -> bool:
    deadline = asset.retention_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=UTC)
    return deadline <= utcnow()


def workspace_list(session: Session, principal: Principal) -> dict[str, Any]:
    return {
        "items": [
            {
                "id": str(principal.organization_id),
                "name": principal.organization_name,
                "roles": sorted(principal.roles),
                "fixture_user": {
                    "id": str(principal.user_id),
                    "email": principal.email,
                    "display_name": principal.display_name,
                },
            }
        ]
    }


def capabilities(
    end_user_region: str = "IN",
    media_processing: dict[str, str] | None = None,
) -> dict[str, Any]:
    region = end_user_region.upper()
    return {
        "invocation_mode": "fixture",
        "media_processing": media_processing
        or {
            "mode": "fixture",
            "processor_version": "fixture-media-v1",
        },
        "operator_region": "IN",
        "deployment_region": "local-IN",
        "end_user_region": region,
        "items": [
            {
                "family": "Spark",
                "role": "structured Check reasoning over authorized evidence",
                "status": "ready",
                "reason": "Deterministic fixture available; live access remains unverified.",
                "live_verified": False,
            },
            {
                "family": "Voice Transcribe",
                "role": "time-aligned speech evidence",
                "status": "ready",
                "reason": "Deterministic fixture available; live access remains unverified.",
                "live_verified": False,
            },
            {
                "family": "SAM",
                "role": "sampled visual and product-concept evidence",
                "status": "ready",
                "reason": "Deterministic fixture available; live access remains unverified.",
                "live_verified": False,
            },
            {
                "family": "Wonder",
                "role": "bounded read-only campaign evidence dossier",
                "status": "awaiting_access",
                "reason": "The bounded dossier role is defined; execution awaits verified access.",
                "live_verified": False,
            },
            {
                "family": "Muse Image",
                "role": "conditional eyewear preview",
                "status": "policy_restricted",
                "reason": (
                    "The current operator/deployment context is India; "
                    "no upload or call is allowed."
                ),
                "policy_version": "meta-geographic-use-policy-checked-2026-10-21",
                "live_verified": False,
            },
        ],
    }


def catalog_products(session: Session, principal: Principal) -> dict[str, Any]:
    products = session.scalars(
        select(Product)
        .where(Product.organization_id == principal.organization_id)
        .order_by(Product.name)
    ).all()
    return {
        "items": [
            {
                "id": str(item.id),
                "name": item.name,
                "category": item.category,
                "sku": item.sku,
                "version": item.version,
            }
            for item in products
        ]
    }


def catalog_creators(
    session: Session,
    principal: Principal,
    *,
    query: str | None = None,
    category: str | None = None,
    match_kind: CreatorMatchKind | None = None,
    permission_status: CreatorPermissionStatus | None = None,
    verification_status: CreatorVerificationStatus | None = None,
    product_id: UUID | None = None,
) -> dict[str, Any]:
    filters: list[Any] = [
        Creator.organization_id == principal.organization_id,
        CreatorEvidence.organization_id == principal.organization_id,
    ]
    if query and (term := query.strip().lower()):
        filters.append(
            or_(
                func.lower(Creator.name).contains(term, autoescape=True),
                func.lower(Creator.handle).contains(term, autoescape=True),
                func.lower(CreatorEvidence.description).contains(term, autoescape=True),
                func.lower(CreatorEvidence.source_label).contains(term, autoescape=True),
            )
        )
    if category and (category_name := category.strip().lower()):
        filters.append(func.lower(CreatorEvidence.category) == category_name)
    if match_kind is not None:
        filters.append(CreatorEvidence.match_kind == match_kind)
    if permission_status is not None:
        filters.append(CreatorEvidence.permission_status == permission_status)
    if verification_status is not None:
        filters.append(CreatorEvidence.verification_status == verification_status)
    if product_id is not None:
        product = session.scalar(
            select(Product).where(
                Product.id == product_id,
                Product.organization_id == principal.organization_id,
            )
        )
        if product is None:
            raise not_found()
        filters.append(
            or_(
                and_(
                    CreatorEvidence.match_kind == "exact_product",
                    CreatorEvidence.product_id == product.id,
                ),
                and_(
                    CreatorEvidence.match_kind == "category_relevance",
                    func.lower(CreatorEvidence.category) == product.category.lower(),
                ),
            )
        )

    rows = session.execute(
        select(Creator, CreatorEvidence)
        .join(
            CreatorEvidence,
            and_(
                CreatorEvidence.creator_id == Creator.id,
                CreatorEvidence.organization_id == Creator.organization_id,
            ),
        )
        .where(*filters)
        .order_by(Creator.name, CreatorEvidence.captured_at.desc(), CreatorEvidence.id)
    ).all()
    creators: dict[UUID, dict[str, Any]] = {}
    for creator, evidence in rows:
        item = creators.setdefault(
            creator.id,
            {
                "id": str(creator.id),
                "name": creator.name,
                "handle": creator.handle,
                "rights_status": creator.rights_status,
                "evidence_timestamp": creator.evidence_timestamp,
                "evidence": [],
            },
        )
        item["evidence"].append(
            {
                "id": str(evidence.id),
                "product_id": str(evidence.product_id) if evidence.product_id else None,
                "category": evidence.category,
                "match_kind": evidence.match_kind,
                "source_kind": evidence.source_kind,
                "source_uri": evidence.source_uri,
                "source_label": evidence.source_label,
                "permission_status": evidence.permission_status,
                "verification_status": evidence.verification_status,
                "evidence_mode": evidence.evidence_mode,
                "description": evidence.description,
                "captured_at": evidence.captured_at,
            }
        )
    return {"collection": "curated", "items": list(creators.values())}


def catalog_rule_packs(session: Session, principal: Principal) -> dict[str, Any]:
    packs = session.scalars(
        select(RulePackVersion)
        .where(RulePackVersion.organization_id == principal.organization_id)
        .order_by(RulePackVersion.name)
    ).all()
    return {
        "items": [
            {
                "id": str(item.id),
                "name": item.name,
                "version": item.version,
                "status": item.status,
                "source_uri": item.source_uri,
                "content_hash": item.content_hash,
                "rules": item.rules,
            }
            for item in packs
        ]
    }


def campaign_dict(session: Session, campaign: Campaign) -> dict[str, Any]:
    product = session.get(Product, campaign.product_id)
    pack = session.get(RulePackVersion, campaign.rule_pack_version_id)
    creator_ids = session.scalars(
        select(CampaignCreator.creator_id).where(CampaignCreator.campaign_id == campaign.id)
    ).all()
    submission_count = session.scalar(
        select(func.count(Submission.id)).where(
            Submission.campaign_id == campaign.id,
            Submission.deleted_at.is_(None),
        )
    )
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "objective": campaign.objective,
        "market": campaign.market,
        "product": {
            "id": str(product.id),
            "name": product.name,
            "sku": product.sku,
        }
        if product
        else None,
        "rule_pack": {
            "id": str(pack.id),
            "name": pack.name,
            "version": pack.version,
            "status": pack.status,
            "source_uri": pack.source_uri,
        }
        if pack
        else None,
        "creator_ids": [str(value) for value in creator_ids],
        "submission_count": submission_count or 0,
        "invocation_mode": "fixture",
        "created_at": campaign.created_at,
    }


def campaign_readiness(
    session: Session,
    principal: Principal,
    campaign_id: UUID,
) -> dict[str, Any]:
    campaign = get_campaign(session, principal, campaign_id)
    base_href = f"/campaigns/{campaign.id}"
    submissions = session.scalars(
        select(Submission)
        .where(
            Submission.organization_id == principal.organization_id,
            Submission.campaign_id == campaign.id,
            Submission.deleted_at.is_(None),
        )
        .order_by(Submission.created_at)
    ).all()
    items: list[dict[str, Any]] = []

    def add_item(
        *,
        item_id: str,
        severity: str,
        category: str,
        title: str,
        detail: str,
        action_label: str,
        source_type: str,
        source_id: UUID,
        label: str,
        anchor: str,
    ) -> None:
        items.append(
            {
                "id": item_id,
                "severity": severity,
                "category": category,
                "title": title,
                "detail": detail,
                "action_label": action_label,
                "citation": {
                    "source_type": source_type,
                    "source_id": source_id,
                    "label": label,
                    "href": f"{base_href}#{anchor}",
                },
            }
        )

    if not submissions:
        add_item(
            item_id="campaign:no-draft",
            severity="blocker",
            category="upload",
            title="No creator draft is ready for review",
            detail="Upload an authorized draft before Check can produce evidence.",
            action_label="Open upload",
            source_type="campaign",
            source_id=campaign.id,
            label=campaign.name,
            anchor="submission-upload",
        )

    for submission in submissions:
        version = session.get(SubmissionVersion, submission.current_version_id)
        if version is None:
            add_item(
                item_id=f"submission:{submission.id}:no-version",
                severity="blocker",
                category="upload",
                title="A creator submission has no current version",
                detail="Complete the authorized upload before starting Check.",
                action_label="Open submission",
                source_type="submission",
                source_id=submission.id,
                label="Submission awaiting a version",
                anchor="submission-upload",
            )
            continue
        analysis = session.scalar(
            select(Analysis)
            .where(
                Analysis.organization_id == principal.organization_id,
                Analysis.submission_version_id == version.id,
            )
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        if analysis is None:
            add_item(
                item_id=f"version:{version.id}:unchecked",
                severity="action",
                category="check",
                title=f"Version {version.version_no} has not been checked",
                detail="Run Check for this exact media and caption version.",
                action_label="Run Check",
                source_type="submission_version",
                source_id=version.id,
                label=f"Submission version {version.version_no}",
                anchor="check-launch-heading",
            )
            continue
        if analysis.analysis_status != "completed":
            add_item(
                item_id=f"analysis:{analysis.id}:status",
                severity="blocker",
                category="check",
                title=f"Check is {analysis.analysis_status.replace('_', ' ')}",
                detail="Approval requires a completed Check for all required evidence.",
                action_label="Inspect Check",
                source_type="analysis",
                source_id=analysis.id,
                label=f"Check {analysis.id}",
                anchor="evidence-heading",
            )
        missing = sorted(set(analysis.required_coverage) - set(analysis.observed_coverage))
        if missing:
            add_item(
                item_id=f"analysis:{analysis.id}:coverage",
                severity="blocker",
                category="evidence",
                title="Required evidence is incomplete",
                detail=f"Missing coverage: {', '.join(missing)}.",
                action_label="Review evidence gaps",
                source_type="analysis",
                source_id=analysis.id,
                label=f"Check evidence {analysis.id}",
                anchor="evidence-heading",
            )
        findings = session.scalars(
            select(Finding).where(
                Finding.organization_id == principal.organization_id,
                Finding.analysis_id == analysis.id,
            )
        ).all()
        unresolved = 0
        blocking = 0
        for finding in findings:
            decision = latest_decision(session, finding.id)
            if decision is None:
                unresolved += 1
            elif decision.decision not in {"dismissed", "incorrect"}:
                blocking += 1
        if unresolved or blocking:
            parts = []
            if unresolved:
                parts.append(f"{unresolved} awaiting a reviewer decision")
            if blocking:
                parts.append(f"{blocking} still requiring a content fix")
            add_item(
                item_id=f"analysis:{analysis.id}:findings",
                severity="blocker",
                category="review",
                title="Finding decisions still block approval",
                detail="; ".join(parts) + ".",
                action_label="Review findings",
                source_type="analysis",
                source_id=analysis.id,
                label=f"Check findings {analysis.id}",
                anchor="findings-heading",
            )
        context = session.scalar(
            select(ReviewContext).where(
                ReviewContext.organization_id == principal.organization_id,
                ReviewContext.analysis_id == analysis.id,
            )
        )
        if context is None:
            add_item(
                item_id=f"analysis:{analysis.id}:review-missing",
                severity="blocker",
                category="review",
                title="Review context is unavailable",
                detail="The Check cannot receive a human decision until its review context exists.",
                action_label="Inspect Check",
                source_type="analysis",
                source_id=analysis.id,
                label=f"Check {analysis.id}",
                anchor="approval-heading",
            )
        elif context.review_status == "approved":
            add_item(
                item_id=f"review:{context.id}:approved",
                severity="ready",
                category="review",
                title=f"Version {version.version_no} has current human approval",
                detail="The approval is bound to this version's immutable manifest.",
                action_label="View approval",
                source_type="review_context",
                source_id=context.id,
                label=f"Approved review revision {context.revision}",
                anchor="approval-heading",
            )
        elif (
            not unresolved
            and not blocking
            and analysis.analysis_status == "completed"
            and not missing
        ):
            status_copy = {
                "unreviewed": "The completed Check is waiting for a human decision.",
                "changes_requested": "A reviewer requested a revised creator draft.",
                "rejected": "The current version was rejected and needs a new version.",
                "revoked": (
                    "The prior approval was revoked; this version is not currently approved."
                ),
                "superseded": "A newer version requires its own Check and review.",
            }.get(context.review_status, "The current review needs attention.")
            add_item(
                item_id=f"review:{context.id}:{context.review_status}",
                severity="action",
                category="review",
                title=f"Human review is {context.review_status.replace('_', ' ')}",
                detail=status_copy,
                action_label="Open human review",
                source_type="review_context",
                source_id=context.id,
                label=f"Review revision {context.revision}",
                anchor="approval-heading",
            )

    asset_ids = select(MediaAsset.id).where(
        MediaAsset.organization_id == principal.organization_id,
        MediaAsset.campaign_id == campaign.id,
    )
    submission_ids = select(Submission.id).where(
        Submission.organization_id == principal.organization_id,
        Submission.campaign_id == campaign.id,
    )
    pending_cleanup = session.scalars(
        select(DeletionRequest).where(
            DeletionRequest.organization_id == principal.organization_id,
            DeletionRequest.status != "completed",
            or_(
                (DeletionRequest.resource_type == "media_asset")
                & DeletionRequest.resource_id.in_(asset_ids),
                (DeletionRequest.resource_type == "submission")
                & DeletionRequest.resource_id.in_(submission_ids),
            ),
        )
    ).all()
    for deletion in pending_cleanup:
        add_item(
            item_id=f"deletion:{deletion.id}",
            severity="action",
            category="cleanup",
            title="Data cleanup still needs attention",
            detail=(
                f"Deletion is {deletion.status.replace('_', ' ')} after "
                f"{deletion.attempt_count} attempt(s)."
            ),
            action_label="Review cleanup",
            source_type="deletion_request",
            source_id=deletion.id,
            label=f"Deletion request {deletion.id}",
            anchor="privacy-controls",
        )

    severity_rank = {"blocker": 0, "action": 1, "ready": 2}
    items.sort(key=lambda item: (severity_rank[item["severity"]], item["id"]))
    blocker_count = sum(item["severity"] == "blocker" for item in items)
    action_count = sum(item["severity"] == "action" for item in items)
    ready = bool(submissions) and blocker_count == 0 and action_count == 0
    if ready:
        summary = "Every current creator version has a completed Check and current human approval."
    elif blocker_count:
        summary = (
            f"{blocker_count} blocking issue(s) must be resolved before this campaign is ready."
        )
    else:
        summary = f"{action_count} next action(s) remain before this campaign is ready."
    return {
        "campaign_id": campaign.id,
        "generation_mode": "deterministic_records",
        "ready": ready,
        "blocker_count": blocker_count,
        "action_count": action_count,
        "summary": summary,
        "items": items,
        "limitations": [
            "This brief is derived from authorized Vouch records and does not invoke Wonder.",
            "It cannot certify legal compliance, approve content, publish content, or "
            "contact creators.",
        ],
    }


def _product_claim_dict(claim: ProductClaim) -> dict[str, Any]:
    status = claim.status
    if claim.expires_at is not None and _as_utc(claim.expires_at) <= utcnow():
        status = "expired"
    return {
        "id": claim.id,
        "product_id": claim.product_id,
        "approved_wording": claim.approved_wording,
        "evidence_label": claim.evidence_label,
        "evidence_uri": claim.evidence_uri,
        "expires_at": _as_utc(claim.expires_at) if claim.expires_at else None,
        "status": status,
        "created_at": _as_utc(claim.created_at),
    }


def list_product_claims(
    session: Session, principal: Principal, product_id: UUID
) -> list[dict[str, Any]]:
    product = session.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == principal.organization_id,
        )
    )
    if product is None:
        raise not_found()
    claims = session.scalars(
        select(ProductClaim)
        .where(
            ProductClaim.organization_id == principal.organization_id,
            ProductClaim.product_id == product.id,
        )
        .order_by(ProductClaim.created_at.desc())
    ).all()
    return [_product_claim_dict(claim) for claim in claims]


def create_product_claim(
    session: Session,
    principal: Principal,
    product_id: UUID,
    payload: ProductClaimCreate,
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    product = session.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.organization_id == principal.organization_id,
        )
    )
    if product is None:
        raise not_found()
    if payload.expires_at is not None and payload.expires_at <= utcnow():
        raise unprocessable(
            "INVALID_CLAIM_EXPIRY", "Claim evidence expiry must be in the future."
        )
    claim = ProductClaim(
        organization_id=principal.organization_id,
        product_id=product.id,
        approved_wording=payload.approved_wording.strip(),
        evidence_label=payload.evidence_label.strip(),
        evidence_uri=payload.evidence_uri.strip(),
        expires_at=payload.expires_at,
        status="approved",
        created_by=principal.user_id,
    )
    session.add(claim)
    session.flush()
    audit(
        session,
        principal,
        "product_claim.created",
        "product_claim",
        claim.id,
        {"product_id": str(product.id), "has_expiry": claim.expires_at is not None},
    )
    session.commit()
    return _product_claim_dict(claim)


def _campaign_requirement_dict(requirement: CampaignRequirement) -> dict[str, Any]:
    return {
        "id": requirement.id,
        "campaign_id": requirement.campaign_id,
        "kind": requirement.kind,
        "label": requirement.label,
        "expected_text": requirement.expected_text,
        "claim_id": requirement.claim_id,
        "required": requirement.required,
        "created_at": _as_utc(requirement.created_at),
    }


def create_campaign_requirement(
    session: Session,
    principal: Principal,
    campaign_id: UUID,
    payload: CampaignRequirementCreate,
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    campaign = get_campaign(session, principal, campaign_id)
    if payload.claim_id is not None:
        claim = session.scalar(
            select(ProductClaim).where(
                ProductClaim.id == payload.claim_id,
                ProductClaim.organization_id == principal.organization_id,
                ProductClaim.product_id == campaign.product_id,
            )
        )
        if claim is None:
            raise unprocessable(
                "CLAIM_UNAVAILABLE",
                "Approved claim is unavailable for this campaign product.",
            )
        if _product_claim_dict(claim)["status"] != "approved":
            raise unprocessable(
                "CLAIM_NOT_CURRENT", "Approved claim evidence is no longer current."
            )
    requirement = CampaignRequirement(
        organization_id=principal.organization_id,
        campaign_id=campaign.id,
        kind=payload.kind,
        label=payload.label.strip(),
        expected_text=(payload.expected_text.strip() if payload.expected_text else None),
        claim_id=payload.claim_id,
        required=payload.required,
        created_by=principal.user_id,
    )
    session.add(requirement)
    session.flush()
    audit(
        session,
        principal,
        "campaign_requirement.created",
        "campaign_requirement",
        requirement.id,
        {"campaign_id": str(campaign.id), "kind": requirement.kind},
    )
    session.commit()
    return _campaign_requirement_dict(requirement)


def _requirement_assessment(
    session: Session,
    requirement: CampaignRequirement,
    submission: Submission,
    version: SubmissionVersion,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "requirement_id": requirement.id,
        "submission_id": submission.id,
        "submission_version_id": version.id,
        "analysis_id": None,
        "status": "unknown",
        "detail": "This requirement has not been evaluated for the current version.",
        "evidence_ids": [],
    }
    if requirement.kind in {"cta", "exact_phrase", "approved_claim"}:
        expected = requirement.expected_text
        if requirement.kind == "approved_claim" and requirement.claim_id is not None:
            claim = session.get(ProductClaim, requirement.claim_id)
            if claim is None or _product_claim_dict(claim)["status"] != "approved":
                base["detail"] = "The linked claim evidence is unavailable or expired."
                return base
            expected = claim.approved_wording
        if expected is None:
            base["detail"] = "No expected wording is configured."
            return base
        if expected.casefold() in version.caption.casefold():
            base["status"] = "observed"
            base["detail"] = "The configured wording appears in the exact caption snapshot."
        else:
            base["status"] = "missing"
            base["detail"] = "The configured wording was not found in the caption snapshot."
        return base

    analysis = session.scalar(
        select(Analysis)
        .where(
            Analysis.organization_id == requirement.organization_id,
            Analysis.submission_version_id == version.id,
        )
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    if analysis is None:
        base["detail"] = "Run Check for this exact version before evaluating this requirement."
        return base
    base["analysis_id"] = analysis.id
    modality = "speech" if requirement.kind == "disclosure" else "visual"
    evidence = session.scalars(
        select(EvidenceItem).where(
            EvidenceItem.organization_id == requirement.organization_id,
            EvidenceItem.analysis_id == analysis.id,
            EvidenceItem.modality == modality,
        )
    ).all()
    base["evidence_ids"] = [item.id for item in evidence]
    if analysis.analysis_status != "completed" or modality not in analysis.observed_coverage:
        base["detail"] = f"{modality.title()} evidence is incomplete, so the result is unknown."
        return base
    rule_id = "DISCLOSURE_AUDIO" if requirement.kind == "disclosure" else "PRODUCT_VISIBILITY"
    finding = session.scalar(
        select(Finding).where(
            Finding.organization_id == requirement.organization_id,
            Finding.analysis_id == analysis.id,
            Finding.rule_id == rule_id,
        )
    )
    if finding is not None:
        decision = latest_decision(session, finding.id)
        if decision is None or decision.decision not in {"dismissed", "incorrect"}:
            base["status"] = "missing"
            base["detail"] = (
                "Check found evidence that this requirement still needs review or a fix."
            )
            return base
    base["status"] = "observed"
    base["detail"] = (
        "Check observed the required modality; exact product identity still requires human review."
        if requirement.kind == "product_visibility"
        else "Check found complete speech coverage with no unresolved disclosure finding."
    )
    return base


def campaign_brief(
    session: Session, principal: Principal, campaign_id: UUID
) -> dict[str, Any]:
    campaign = get_campaign(session, principal, campaign_id)
    claims = session.scalars(
        select(ProductClaim)
        .where(
            ProductClaim.organization_id == principal.organization_id,
            ProductClaim.product_id == campaign.product_id,
        )
        .order_by(ProductClaim.created_at.desc())
    ).all()
    requirements = session.scalars(
        select(CampaignRequirement)
        .where(
            CampaignRequirement.organization_id == principal.organization_id,
            CampaignRequirement.campaign_id == campaign.id,
        )
        .order_by(CampaignRequirement.created_at)
    ).all()
    submissions = session.scalars(
        select(Submission).where(
            Submission.organization_id == principal.organization_id,
            Submission.campaign_id == campaign.id,
            Submission.deleted_at.is_(None),
        )
    ).all()
    assessments: list[dict[str, Any]] = []
    for requirement in requirements:
        if not submissions:
            assessments.append(
                {
                    "requirement_id": requirement.id,
                    "submission_id": None,
                    "submission_version_id": None,
                    "analysis_id": None,
                    "status": "unknown",
                    "detail": "No current creator draft is available.",
                    "evidence_ids": [],
                }
            )
            continue
        for submission in submissions:
            version = session.get(SubmissionVersion, submission.current_version_id)
            if version is None:
                assessments.append(
                    {
                        "requirement_id": requirement.id,
                        "submission_id": submission.id,
                        "submission_version_id": None,
                        "analysis_id": None,
                        "status": "unknown",
                        "detail": "The submission has no current version.",
                        "evidence_ids": [],
                    }
                )
                continue
            assessments.append(_requirement_assessment(session, requirement, submission, version))
    return {
        "campaign_id": campaign.id,
        "claims": [_product_claim_dict(claim) for claim in claims],
        "requirements": [_campaign_requirement_dict(item) for item in requirements],
        "assessments": assessments,
        "limitations": [
            "Caption wording checks are exact text matches, not semantic claim certification.",
            "Fixture visual and speech observations do not prove product identity or legal "
            "compliance.",
            "Missing or incomplete evidence is reported as unknown, never as a pass.",
        ],
    }


def create_campaign(
    session: Session, principal: Principal, payload: CampaignCreate
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    product = session.scalar(
        select(Product).where(
            Product.id == payload.product_id,
            Product.organization_id == principal.organization_id,
        )
    )
    pack = session.scalar(
        select(RulePackVersion).where(
            RulePackVersion.id == payload.rule_pack_version_id,
            RulePackVersion.organization_id == principal.organization_id,
        )
    )
    if product is None or pack is None:
        raise not_found()
    creators = session.scalars(
        select(Creator).where(
            Creator.id.in_(payload.creator_ids),
            Creator.organization_id == principal.organization_id,
        )
    ).all()
    if len(creators) != len(set(payload.creator_ids)):
        raise not_found()
    campaign = Campaign(
        organization_id=principal.organization_id,
        name=payload.name.strip(),
        objective=payload.objective.strip(),
        market=payload.market.upper(),
        product_id=product.id,
        rule_pack_version_id=pack.id,
        created_by=principal.user_id,
    )
    session.add(campaign)
    session.flush()
    for creator in creators:
        session.add(
            CampaignCreator(
                organization_id=principal.organization_id,
                campaign_id=campaign.id,
                creator_id=creator.id,
            )
        )
    audit(session, principal, "campaign.created", "campaign", campaign.id)
    session.commit()
    return campaign_dict(session, campaign)


def add_campaign_creator(
    session: Session,
    principal: Principal,
    campaign_id: UUID,
    payload: CampaignCreatorCreate,
) -> tuple[dict[str, Any], bool]:
    require_roles(principal, "admin", "marketer")
    campaign = get_campaign(session, principal, campaign_id)
    creator = session.scalar(
        select(Creator).where(
            Creator.id == payload.creator_id,
            Creator.organization_id == principal.organization_id,
        )
    )
    evidence = session.scalar(
        select(CreatorEvidence).where(
            CreatorEvidence.id == payload.evidence_id,
            CreatorEvidence.creator_id == payload.creator_id,
            CreatorEvidence.organization_id == principal.organization_id,
        )
    )
    if creator is None or evidence is None:
        raise not_found()
    if (
        evidence.permission_status == "permission_unknown"
        or evidence.verification_status == "unavailable"
    ):
        raise conflict(
            "CREATOR_EVIDENCE_NOT_ELIGIBLE",
            "Select evidence with recorded permission and an available verification state.",
        )
    product = session.scalar(
        select(Product).where(
            Product.id == campaign.product_id,
            Product.organization_id == principal.organization_id,
        )
    )
    if product is None:
        raise not_found()
    evidence_matches_campaign = (
        evidence.match_kind == "exact_product" and evidence.product_id == product.id
    ) or (
        evidence.match_kind == "category_relevance"
        and evidence.category.strip().casefold() == product.category.strip().casefold()
    )
    if not evidence_matches_campaign:
        raise conflict(
            "CREATOR_EVIDENCE_CAMPAIGN_MISMATCH",
            "Select evidence that matches this campaign's exact product or product category.",
        )

    query = select(CampaignCreator).where(
        CampaignCreator.organization_id == principal.organization_id,
        CampaignCreator.campaign_id == campaign.id,
        CampaignCreator.creator_id == creator.id,
    )
    assignment = session.scalar(query)
    created = assignment is None
    if assignment is None:
        assignment = CampaignCreator(
            organization_id=principal.organization_id,
            campaign_id=campaign.id,
            creator_id=creator.id,
            evidence_id=evidence.id,
        )
        try:
            with session.begin_nested():
                session.add(assignment)
                session.flush()
        except IntegrityError:
            assignment = session.scalar(query.execution_options(populate_existing=True))
            if assignment is None:
                raise
            created = False

    evidence_linked = False
    if assignment.evidence_id is None:
        assignment.evidence_id = evidence.id
        evidence_linked = True
    elif assignment.evidence_id != evidence.id:
        raise conflict(
            "CAMPAIGN_CREATOR_EVIDENCE_CONFLICT",
            "This creator is already linked to different campaign evidence.",
        )

    if created:
        audit(
            session,
            principal,
            "campaign.creator_added",
            "campaign_creator",
            assignment.id,
            {"campaign_id": str(campaign.id), "evidence_id": str(evidence.id)},
        )
    elif evidence_linked:
        audit(
            session,
            principal,
            "campaign.creator_evidence_linked",
            "campaign_creator",
            assignment.id,
            {"campaign_id": str(campaign.id), "evidence_id": str(evidence.id)},
        )
    if created or evidence_linked:
        session.commit()
    return (
        {
            "id": str(assignment.id),
            "campaign_id": str(assignment.campaign_id),
            "creator_id": str(assignment.creator_id),
            "evidence_id": str(evidence.id),
            "created": created,
        },
        created,
    )


def list_campaigns(session: Session, principal: Principal) -> dict[str, Any]:
    campaigns = session.scalars(
        select(Campaign)
        .where(Campaign.organization_id == principal.organization_id)
        .order_by(Campaign.created_at.desc())
    ).all()
    return {"items": [campaign_dict(session, campaign) for campaign in campaigns]}


def source_authorization_receipt(
    session: Session, asset: MediaAsset, organization_id: UUID
) -> ConsentReceipt | None:
    return session.scalar(
        select(ConsentReceipt)
        .where(
            ConsentReceipt.asset_id == asset.id,
            ConsentReceipt.organization_id == organization_id,
        )
        .execution_options(populate_existing=True)
    )


def source_authorization_active(
    session: Session, asset: MediaAsset, organization_id: UUID
) -> bool:
    receipt = source_authorization_receipt(session, asset, organization_id)
    notice = NOTICE_REGISTRY.get(receipt.notice_version) if receipt else None
    member_actor = bool(
        asset.uploader_user_id is not None
        and asset.uploader_guest_session_id is None
        and receipt is not None
        and receipt.actor_user_id == asset.uploader_user_id
        and receipt.actor_guest_session_id is None
    )
    guest_actor = bool(
        asset.uploader_user_id is None
        and asset.uploader_guest_session_id is not None
        and receipt is not None
        and receipt.actor_user_id is None
        and receipt.actor_guest_session_id == asset.uploader_guest_session_id
    )
    return bool(
        asset.organization_id == organization_id and asset.deleted_at is None
        and asset.rights_attested and not source_expired(asset)
        and receipt is not None and receipt.revoked_at is None
        and receipt.campaign_id == asset.campaign_id
        and (member_actor != guest_actor)
        and receipt.purpose == "campaign_check" and notice is not None
        and receipt.notice_hash == notice.notice_hash
    )


def _require_processing_authorization(
    session: Session, asset: MediaAsset, organization_id: UUID
) -> None:
    if not source_authorization_active(session, asset, organization_id):
        raise conflict(
            "PROCESSING_AUTHORIZATION_REQUIRED",
            "A fresh upload with active processing notice acknowledgment is required.",
        )


def consent_receipt_dict(receipt: ConsentReceipt) -> dict[str, Any]:
    return {
        "id": str(receipt.id), "asset_id": str(receipt.asset_id),
        "campaign_id": str(receipt.campaign_id),
        "actor_user_id": str(receipt.actor_user_id) if receipt.actor_user_id else None,
        "actor_guest_session_id": (
            str(receipt.actor_guest_session_id) if receipt.actor_guest_session_id else None
        ),
        "purpose": receipt.purpose, "notice_version": receipt.notice_version,
        "notice_hash": receipt.notice_hash, "accepted_at": _as_utc(receipt.accepted_at),
        "revoked_at": _as_utc(receipt.revoked_at) if receipt.revoked_at else None,
        "revoked_by": str(receipt.revoked_by) if receipt.revoked_by else None,
        "revocation_actor_kind": receipt.revocation_actor_kind,
        "revocation_reason": receipt.revocation_reason,
    }


def _authorization_dict(session: Session, asset: MediaAsset) -> dict[str, Any]:
    receipt = source_authorization_receipt(session, asset, asset.organization_id)
    return {
        "authorization_status": (
            "legacy_no_notice" if receipt is None else "revoked" if receipt.revoked_at else "active"
        ),
        "consent_receipt": consent_receipt_dict(receipt) if receipt else None,
    }


def upload_intent(
    session: Session, principal: Principal, payload: UploadIntentCreate
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    notice = require_current_notice(payload.notice_version)
    lock_lineage(session, principal.organization_id)
    _current_upload_roles(session, principal)
    get_campaign(session, principal, payload.campaign_id)
    if workspace_storage_usage(session, principal).available_bytes < MAX_MEDIA_BYTES:
        raise conflict(
            "STORAGE_ALLOWANCE_EXCEEDED",
            "Workspace storage is full. Delete unused sources and wait for cleanup "
            "before uploading.",
        )
    upload_token = secrets.token_urlsafe(32)
    finalize_token = secrets.token_urlsafe(32)
    asset_id = uuid4()
    asset = MediaAsset(
        id=asset_id,
        organization_id=principal.organization_id,
        campaign_id=payload.campaign_id,
        uploader_user_id=principal.user_id,
        filename=payload.filename,
        proposed_content_type=payload.content_type,
        expected_bytes=payload.byte_size,
        upload_token_hash=sha256_text(upload_token),
        finalize_token_hash=sha256_text(finalize_token),
        rights_attested=payload.rights_attested,
        retention_deadline=utcnow() + timedelta(days=30),
        storage_backend="supabase" if principal.access_token else "database",
        object_key=(
            f"{principal.organization_id}/{payload.campaign_id}/{asset_id}/source"
            if principal.access_token
            else None
        ),
    )
    session.add(asset)
    session.flush()
    receipt = ConsentReceipt(
        organization_id=principal.organization_id, asset_id=asset.id,
        campaign_id=asset.campaign_id, actor_user_id=principal.user_id,
        purpose=payload.purpose, notice_version=notice.version, notice_hash=notice.notice_hash,
    )
    session.add(receipt)
    session.flush()
    audit(
        session, principal, "processing.authorization_acknowledged", "consent_receipt", receipt.id
    )
    audit(session, principal, "upload.intent_created", "media_asset", asset.id)
    session.commit()
    return {
        "upload_id": str(asset.id),
        "content_url": f"/api/v1/uploads/{asset.id}/content",
        "upload_token": upload_token,
        "finalize_token": finalize_token,
        "required_header": "X-Upload-Token",
        "max_bytes": 5_000_000,
        "expires_at": asset.created_at + timedelta(minutes=5),
        "authorization_status": "active",
        "consent_receipt": consent_receipt_dict(receipt),
    }


def _assert_upload_unexpired(asset: MediaAsset) -> None:
    created_at = asset.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    if utcnow() >= created_at + timedelta(minutes=5):
        raise ApiError(401, "UPLOAD_AUTHORIZATION_EXPIRED", "Create a new upload authorization.")


def upload_content(
    session: Session,
    upload_id: UUID,
    upload_token: str | None,
    content_type: str | None,
    body: bytes,
    principal: Principal | None = None,
) -> dict[str, Any]:
    asset = session.scalar(select(MediaAsset).where(MediaAsset.id == upload_id).with_for_update())
    if asset is None or asset.deleted_at is not None:
        raise not_found()
    if not upload_token or not secrets.compare_digest(
        asset.upload_token_hash, sha256_text(upload_token)
    ):
        raise ApiError(401, "UPLOAD_TOKEN_INVALID", "The upload token is invalid or expired.")
    _assert_upload_unexpired(asset)
    _require_processing_authorization(session, asset, asset.organization_id)
    if asset.status not in {"intent_created", "content_uploaded"}:
        raise conflict(
            "UPLOAD_STATE_CONFLICT", "This upload cannot accept content in its current state."
        )
    normalized_type = (content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if normalized_type != asset.proposed_content_type:
        raise ApiError(
            415, "UNSUPPORTED_MEDIA_TYPE", "Content-Type does not match the upload intent."
        )
    if len(body) != asset.expected_bytes:
        raise unprocessable(
            "UPLOAD_SIZE_MISMATCH",
            "The received byte length does not match the declared upload size.",
        )
    if asset.storage_backend == "supabase":
        if (
            principal is None
            or not principal.access_token
            or not asset.object_key
            or asset.organization_id != principal.organization_id
            or asset.uploader_user_id != principal.user_id
        ):
            raise not_found()
        store: MediaStore = session.info["media_store"]
        if asset.status == "content_uploaded":
            if store.download(asset.object_key, principal.access_token) != body:
                raise conflict(
                    "UPLOAD_CONTENT_CONFLICT", "This upload already has different bytes."
                )
            if asset.sha256 is None:
                asset.sha256 = sha256_bytes(body)
                session.commit()
            return {"upload_id": str(asset.id), "status": asset.status, "received_bytes": len(body)}
        store.upload(asset.object_key, body, normalized_type, principal.access_token)
        asset.object_bytes = None
    else:
        if asset.status == "content_uploaded":
            if asset.object_bytes != body:
                raise conflict(
                    "UPLOAD_CONTENT_CONFLICT", "This upload already has different bytes."
                )
            if asset.sha256 is None:
                asset.sha256 = sha256_bytes(body)
                session.commit()
            return {"upload_id": str(asset.id), "status": asset.status, "received_bytes": len(body)}
        asset.object_bytes = body
    asset.actual_bytes = len(body)
    asset.sha256 = sha256_bytes(body)
    asset.status = "content_uploaded"
    session.commit()
    return {"upload_id": str(asset.id), "status": asset.status, "received_bytes": len(body)}


def _sniff_media(body: bytes) -> str | None:
    if len(body) >= 12 and body[4:8] == b"ftyp":
        return "video/mp4"
    if body.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    return None


def finalize_upload(
    session: Session, principal: Principal, upload_id: UUID, finalize_token: str
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    asset = _finalization_source(session, principal, upload_id, finalize_token)
    if asset.status == "validated":
        return media_asset_dict(session, asset)
    if asset.status != "content_uploaded":
        raise conflict("UPLOAD_NOT_READY", "Upload content must be received before finalization.")
    processor: MediaProcessor = session.info["media_processor"]
    if asset.processing_container:
        if asset.processing_lease_until and _as_utc(asset.processing_lease_until) > utcnow():
            raise conflict(
                "MEDIA_PROCESSING_IN_PROGRESS", "Media validation is already in progress."
            )
        remove_sandbox_container(asset.processing_container, principal.organization_id)
    # Prepare an EMPTY container while the source is locked. Deletion can now remove its
    # durable identity before media enters it; a late start cannot recreate a removed name.
    prepared = processor.prepare(asset.proposed_content_type, principal.organization_id, asset.id)
    if prepared is not None:
        asset.processing_container = prepared.name
        asset.processing_lease_until = utcnow() + timedelta(seconds=60)
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
    # SQLite BEGIN IMMEDIATE also holds a write lock: commit before any untrusted work.
    session.commit()
    try:
        body, detected, processed = _process_staged_media(
            session, principal, snapshot, body, processor, prepared,
        )
    finally:
        if prepared is not None:
            remove_sandbox_container(prepared.name, principal.organization_id)
    original_hash = sha256_bytes(body)
    metadata = processed.model_dump(mode="json")
    # Publication follows the same tenant lineage gate as attachment/revision/deletion.
    lock_lineage(session, principal.organization_id)
    asset = _finalization_source(session, principal, upload_id, finalize_token)
    if any(getattr(asset, key) != value for key, value in snapshot.items() if key != "sha256"):
        raise conflict(
            "UPLOAD_CONTENT_CONFLICT", "The authorized upload changed during processing."
        )
    if asset.status == "validated":
        if asset.sha256 == original_hash and asset.processing_metadata == metadata:
            return media_asset_dict(session, asset)
        raise conflict("UPLOAD_STATE_CONFLICT", "The asset was finalized with different metadata.")
    if asset.sha256 != snapshot["sha256"]:
        raise conflict(
            "UPLOAD_CONTENT_CONFLICT", "The authorized upload changed during processing."
        )
    if asset.status != "content_uploaded":
        raise conflict("UPLOAD_NOT_READY", "The upload is no longer available for finalization.")
    if asset.storage_backend == "database" and asset.object_bytes != body:
        raise conflict("UPLOAD_CONTENT_CONFLICT", "Stored media changed during processing.")
    asset.validated_content_type = detected
    asset.sha256 = original_hash
    asset.duration_ms = processed.duration_ms
    asset.processing_metadata = metadata
    asset.status = "validated"
    audit(
        session, principal, "upload.validated", "media_asset", asset.id,
        {"bytes": asset.actual_bytes, "validated_content_type": detected,
         "media_mode": processed.mode, "processor_version": processed.processor_version},
    )
    session.commit()
    return media_asset_dict(session, asset)


def _process_staged_media(
    session: Session,
    principal: Principal,
    snapshot: dict[str, Any],
    body: bytes | None,
    processor: MediaProcessor,
    prepared: PreparedMedia | None,
) -> tuple[bytes, str, ProcessedMedia]:
    if snapshot["storage_backend"] == "supabase":
        object_key = snapshot["object_key"]
        if not principal.access_token or not object_key:
            raise not_found()
        store: MediaStore = session.info["media_store"]
        body = store.download(object_key, principal.access_token)
    return _validate_staged_media(body, snapshot, processor, prepared)


def _validate_staged_media(
    body: bytes | None,
    snapshot: dict[str, Any],
    processor: MediaProcessor,
    prepared: PreparedMedia | None,
) -> tuple[bytes, str, ProcessedMedia]:
    """Validate immutable staged bytes without assuming a member or guest actor."""
    if body is None or len(body) != snapshot["expected_bytes"]:
        raise conflict("UPLOAD_NOT_READY", "Stored media does not match the authorized upload.")
    original_hash = sha256_bytes(body)
    if snapshot["sha256"] and snapshot["sha256"] != original_hash:
        raise conflict("UPLOAD_CONTENT_CONFLICT", "Stored media differs from the received bytes.")
    detected = _sniff_media(body)
    if detected is None or detected != snapshot["proposed_content_type"]:
        raise ApiError(
            415, "MEDIA_MAGIC_MISMATCH", "The media signature is unsupported or mismatched."
        )
    return body, detected, processor.process(body, detected, prepared)


def _finalization_source(
    session: Session,
    principal: Principal,
    upload_id: UUID,
    finalize_token: str,
) -> MediaAsset:
    # Re-read membership/roles after the decoder: the original Principal is a snapshot.
    roles = _current_upload_roles(session, principal)
    asset = session.scalar(
        select(MediaAsset)
        .where(
            MediaAsset.id == upload_id,
            MediaAsset.organization_id == principal.organization_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if asset is None or asset.deleted_at is not None or asset.status == "deleted":
        raise not_found()
    if asset.uploader_user_id != principal.user_id and "admin" not in roles:
        raise not_found()
    if not secrets.compare_digest(asset.finalize_token_hash, sha256_text(finalize_token)):
        raise ApiError(401, "FINALIZE_TOKEN_INVALID", "The finalization token is invalid.")
    _assert_upload_unexpired(asset)
    if source_expired(asset):
        raise conflict("RESOURCE_EXPIRED", "The source retention deadline has passed.")
    if not asset.rights_attested:
        raise unprocessable("RIGHTS_ATTESTATION_REQUIRED", "Source rights must be attested.")
    _require_processing_authorization(session, asset, principal.organization_id)
    if session.scalar(
        select(Tombstone.id).where(
            Tombstone.organization_id == principal.organization_id,
            Tombstone.resource_type == "media_asset",
            Tombstone.resource_id == asset.id,
        )
    ):
        raise not_found()
    return asset


def _current_upload_roles(session: Session, principal: Principal) -> set[str]:
    membership = session.scalar(
        select(Membership)
        .where(
            Membership.organization_id == principal.organization_id,
            Membership.user_id == principal.user_id,
            Membership.active.is_(True),
        )
        .execution_options(populate_existing=True)
    )
    if membership is None:
        raise ApiError(403, "MEMBERSHIP_INACTIVE", "No active membership was found.")
    roles = set(
        session.scalars(
            select(MembershipRole.role).where(
                MembershipRole.membership_id == membership.id,
                MembershipRole.organization_id == principal.organization_id,
            )
        )
    )
    if roles.isdisjoint({"admin", "marketer"}):
        raise ApiError(403, "FORBIDDEN", "This action is not permitted for your role.")
    return roles


def media_asset_dict(session: Session, asset: MediaAsset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "campaign_id": str(asset.campaign_id),
        "status": asset.status,
        "storage_backend": asset.storage_backend,
        "content_type": asset.validated_content_type,
        "byte_size": asset.actual_bytes,
        "sha256": asset.sha256,
        "duration_ms": asset.duration_ms,
        "processing_metadata": asset.processing_metadata,
        "retention_deadline": asset.retention_deadline,
        "deleted_at": asset.deleted_at,
        **_authorization_dict(session, asset),
    }


def _validated_asset(
    session: Session, principal: Principal, asset_id: UUID, campaign_id: UUID
) -> MediaAsset:
    asset = session.scalar(
        select(MediaAsset)
        .where(
            MediaAsset.id == asset_id,
            MediaAsset.organization_id == principal.organization_id,
            MediaAsset.campaign_id == campaign_id,
            MediaAsset.status == "validated",
            MediaAsset.deleted_at.is_(None),
            MediaAsset.retention_deadline > utcnow(),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if asset is None:
        raise unprocessable(
            "ASSET_NOT_VALIDATED", "A finalized, validated campaign asset is required."
        )
    _require_processing_authorization(session, asset, principal.organization_id)
    return asset


def _creator(session: Session, principal: Principal, creator_id: UUID) -> Creator:
    creator = session.scalar(
        select(Creator).where(
            Creator.id == creator_id,
            Creator.organization_id == principal.organization_id,
        )
    )
    if creator is None:
        raise not_found()
    return creator


def lock_lineage(session: Session, organization_id: UUID) -> None:
    # ponytail: serialize attachment/deletion per tenant; use finer locks if contention warrants it.
    # Separate from budget-row locks: worker budget reconciliation cannot deadlock this gate.
    # SQLite already serializes transactions with BEGIN IMMEDIATE.
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("select pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": f"vouch.lineage.{organization_id}"},
        )


def create_submission(
    session: Session,
    principal: Principal,
    campaign_id: UUID,
    payload: SubmissionCreate,
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    lock_lineage(session, principal.organization_id)
    if not payload.rights_attested:
        raise unprocessable("RIGHTS_ATTESTATION_REQUIRED", "Source rights must be attested.")
    get_campaign(session, principal, campaign_id)
    _creator(session, principal, payload.creator_id)
    asset = _validated_asset(session, principal, payload.asset_id, campaign_id)
    if not asset.rights_attested:
        raise unprocessable("RIGHTS_ATTESTATION_REQUIRED", "Source rights must be attested.")
    submission = Submission(
        organization_id=principal.organization_id,
        campaign_id=campaign_id,
        creator_id=payload.creator_id,
    )
    session.add(submission)
    session.flush()
    version = SubmissionVersion(
        organization_id=principal.organization_id,
        submission_id=submission.id,
        version_no=1,
        asset_id=asset.id,
        media_hash=asset.sha256 or "",
        caption=payload.caption,
        caption_hash=sha256_text(payload.caption),
        uploader_user_id=principal.user_id,
        rights_attested=True,
    )
    session.add(version)
    session.flush()
    submission.current_version_id = version.id
    audit(session, principal, "submission.created", "submission", submission.id)
    session.commit()
    return submission_dict(session, submission)


def create_submission_version(
    session: Session,
    principal: Principal,
    submission_id: UUID,
    payload: SubmissionVersionCreate,
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    lock_lineage(session, principal.organization_id)
    submission = get_submission(session, principal, submission_id, lock=True)
    if submission.deleted_at is not None:
        raise conflict("RESOURCE_DELETED", "A deleted submission cannot be revised.")
    if not payload.rights_attested:
        raise unprocessable("RIGHTS_ATTESTATION_REQUIRED", "Source rights must be attested.")
    asset = _validated_asset(session, principal, payload.asset_id, submission.campaign_id)
    current_max = session.scalar(
        select(func.max(SubmissionVersion.version_no)).where(
            SubmissionVersion.submission_id == submission.id
        )
    )
    version = SubmissionVersion(
        organization_id=principal.organization_id,
        submission_id=submission.id,
        version_no=(current_max or 0) + 1,
        asset_id=asset.id,
        media_hash=asset.sha256 or "",
        caption=payload.caption,
        caption_hash=sha256_text(payload.caption),
        uploader_user_id=principal.user_id,
        rights_attested=True,
    )
    session.add(version)
    now = utcnow()
    contexts = session.scalars(
        select(ReviewContext).where(
            ReviewContext.submission_id == submission.id,
            ReviewContext.review_status != "superseded",
        )
    ).all()
    for context in contexts:
        context.review_status = "superseded"
        context.revision += 1
        context.superseded_at = now
        session.add(
            ReviewEvent(
                organization_id=principal.organization_id,
                review_context_id=context.id,
                action="superseded",
                rationale="A new immutable submission version was created.",
                actor_user_id=principal.user_id,
                review_revision=context.revision,
                manifest_hash=context.manifest_hash,
            )
        )
    session.flush()
    submission.current_version_id = version.id
    audit(
        session,
        principal,
        "submission.version_created",
        "submission_version",
        version.id,
        {"version_no": version.version_no, "superseded_review_count": len(contexts)},
    )
    session.commit()
    return submission_dict(session, submission)


def submission_dict(session: Session, submission: Submission) -> dict[str, Any]:
    versions = session.scalars(
        select(SubmissionVersion)
        .where(SubmissionVersion.submission_id == submission.id)
        .order_by(SubmissionVersion.version_no)
    ).all()
    rows: list[dict[str, Any]] = []
    for version in versions:
        source = session.get(MediaAsset, version.asset_id)
        source_available = (
            source is not None and source.deleted_at is None and not source_expired(source)
        )
        analyses = session.scalars(
            select(Analysis)
            .where(Analysis.submission_version_id == version.id)
            .order_by(Analysis.created_at.desc())
        ).all()
        rows.append(
            {
                "id": str(version.id),
                "version_no": version.version_no,
                "asset_id": str(version.asset_id),
                "media_hash": version.media_hash,
                "caption": version.caption if source_available else "",
                "source_available": source_available,
                "media_processing": source.processing_metadata
                if source_available and source
                else {},
                "duration_ms": source.duration_ms if source_available and source else None,
                **(_authorization_dict(session, source) if source else {
                    "authorization_status": "legacy_no_notice", "consent_receipt": None,
                }),
                "caption_hash": version.caption_hash,
                "created_at": version.created_at,
                "is_current": submission.current_version_id == version.id,
                "checks": [
                    {
                        "id": str(item.id),
                        "analysis_status": item.analysis_status,
                        "machine_assessment": item.machine_assessment,
                        "manifest_hash": item.manifest_hash,
                    }
                    for item in analyses
                ],
            }
        )
    return {
        "id": str(submission.id),
        "campaign_id": str(submission.campaign_id),
        "creator_id": str(submission.creator_id),
        "current_version_id": str(submission.current_version_id),
        "deleted_at": submission.deleted_at,
        "versions": rows,
    }


def list_campaign_submissions(
    session: Session, principal: Principal, campaign_id: UUID
) -> dict[str, Any]:
    get_campaign(session, principal, campaign_id)
    items = session.scalars(
        select(Submission)
        .where(
            Submission.organization_id == principal.organization_id,
            Submission.campaign_id == campaign_id,
            Submission.deleted_at.is_(None),
        )
        .order_by(Submission.created_at.desc())
    ).all()
    return {"items": [submission_dict(session, item) for item in items]}


def _manifest(
    version: SubmissionVersion,
    asset: MediaAsset,
    campaign: Campaign,
    pack: RulePackVersion,
    payload: CheckCreate,
    consent_receipt: ConsentReceipt | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "submission_version_id": str(version.id),
        "media_hash": version.media_hash,
        "caption_hash": version.caption_hash,
        "asset_duration_ms": asset.duration_ms,
        "campaign_id": str(campaign.id),
        "market": campaign.market,
        "rule_pack_version_id": str(pack.id),
        "rule_pack_hash": pack.content_hash,
        "rule_pack_status": pack.status,
        "schema_version": payload.schema_version,
        "prompt_version": PROMPT_VERSION,
        "model_versions": MODEL_VERSIONS,
        "invocation_mode": payload.invocation_mode,
        "scenario": payload.scenario,
    }
    if asset.processing_metadata:
        manifest["media_processing"] = asset.processing_metadata
    if consent_receipt is not None:
        manifest["processing_authorization"] = {
            "receipt_id": str(consent_receipt.id), "purpose": consent_receipt.purpose,
            "notice_version": consent_receipt.notice_version,
            "notice_hash": consent_receipt.notice_hash,
        }
    return manifest


def async_command(job: Job) -> dict[str, Any]:
    return {
        "operation_id": str(job.id),
        "resource_id": str(job.resource_id),
        "status": job.status,
        "status_url": f"/api/v1/jobs/{job.id}",
        "invocation_mode": "fixture",
    }


def create_check(
    session: Session,
    principal: Principal,
    submission_version_id: UUID,
    payload: CheckCreate,
    idempotency_key: str | None,
) -> tuple[dict[str, Any], bool]:
    require_roles(principal, "admin", "marketer")
    if not idempotency_key:
        raise bad_request("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required.")
    if len(idempotency_key) > 160:
        raise bad_request("IDEMPOTENCY_KEY_INVALID", "Idempotency-Key is too long.")
    version = get_submission_version(session, principal, submission_version_id)
    submission = _assert_source_available(session, principal.organization_id, version)
    asset = session.scalar(
        select(MediaAsset).where(
            MediaAsset.id == version.asset_id,
            MediaAsset.organization_id == principal.organization_id,
            MediaAsset.status == "validated",
            MediaAsset.deleted_at.is_(None),
        )
    )
    campaign = get_campaign(session, principal, submission.campaign_id)
    pack = session.scalar(
        select(RulePackVersion).where(
            RulePackVersion.id == campaign.rule_pack_version_id,
            RulePackVersion.organization_id == principal.organization_id,
        )
    )
    if asset is None or pack is None:
        raise unprocessable(
            "CHECK_INPUT_UNAVAILABLE", "Validated input and a pinned rule pack are required."
        )
    _require_processing_authorization(session, asset, principal.organization_id)
    receipt = source_authorization_receipt(session, asset, principal.organization_id)

    # Serialize tenant reservation and deduplication before either is read. Authentication may
    # already have loaded this row, so force the locked database values back into the identity map.
    org = session.scalar(
        select(Organization)
        .where(Organization.id == principal.organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if org is None:
        raise not_found()

    request_hash = stable_hash(
        {"submission_version_id": submission_version_id, **payload.model_dump(mode="json")}
    )
    existing_key = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.organization_id == principal.organization_id,
            IdempotencyRecord.actor_user_id == principal.user_id,
            IdempotencyRecord.operation == "check.create",
            IdempotencyRecord.key == idempotency_key,
        )
    )
    if existing_key:
        if existing_key.request_hash != request_hash:
            raise conflict(
                "IDEMPOTENCY_KEY_REUSED",
                "This Idempotency-Key was already used with a different request.",
            )
        existing_job = session.get(Job, existing_key.job_id)
        if existing_job is None:
            raise RuntimeError("idempotency record references a missing job")
        return async_command(existing_job), False

    manifest = _manifest(version, asset, campaign, pack, payload, receipt)
    manifest_hash = stable_hash(manifest)
    logical_key = f"check:{manifest_hash}"
    existing_job = session.scalar(
        select(Job).where(
            Job.organization_id == principal.organization_id,
            Job.logical_key == logical_key,
        )
    )
    if existing_job:
        session.add(
            IdempotencyRecord(
                organization_id=principal.organization_id,
                actor_user_id=principal.user_id,
                operation="check.create",
                key=idempotency_key,
                request_hash=request_hash,
                job_id=existing_job.id,
                resource_id=existing_job.resource_id,
            )
        )
        session.commit()
        return async_command(existing_job), False

    if (
        org.budget_settled_minor + org.budget_held_minor + CHECK_RESERVATION_MINOR
        > org.budget_cap_minor
    ):
        raise budget_exceeded()
    analysis = Analysis(
        organization_id=principal.organization_id,
        submission_version_id=version.id,
        manifest_hash=manifest_hash,
        invocation_mode="fixture",
        scenario=payload.scenario,
        required_coverage=["speech", "visual"],
        observed_coverage=[],
        missing_intervals=[],
        model_versions=MODEL_VERSIONS,
        prompt_version=PROMPT_VERSION,
        schema_version=payload.schema_version,
    )
    session.add(analysis)
    session.flush()
    job = Job(
        organization_id=principal.organization_id,
        resource_id=analysis.id,
        logical_key=logical_key,
        scenario=payload.scenario,
    )
    session.add(job)
    session.flush()
    analysis.job_id = job.id
    org.budget_held_minor += CHECK_RESERVATION_MINOR
    session.add(
        BudgetReservation(
            organization_id=principal.organization_id,
            job_id=job.id,
            logical_key=logical_key,
            held_minor=CHECK_RESERVATION_MINOR,
            status="held",
        )
    )
    session.add(
        IdempotencyRecord(
            organization_id=principal.organization_id,
            actor_user_id=principal.user_id,
            operation="check.create",
            key=idempotency_key,
            request_hash=request_hash,
            job_id=job.id,
            resource_id=analysis.id,
        )
    )
    audit(
        session,
        principal,
        "check.queued",
        "analysis",
        analysis.id,
        {"job_id": str(job.id), "invocation_mode": "fixture"},
    )
    session.commit()
    return async_command(job), True


def job_dict(job: Job) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "kind": job.kind,
        "resource_id": str(job.resource_id),
        "status": job.status,
        "attempt_count": job.attempt_count,
        "max_attempts": job.max_attempts,
        "retry_after": job.retry_after,
        "last_error": {
            "code": job.last_error_code,
            "message": job.last_error_message,
            "retryable": job.status == "retry_wait",
        }
        if job.last_error_code
        else None,
        "invocation_mode": "fixture",
        "result_url": f"/api/v1/checks/{job.result_id}" if job.result_id else None,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def latest_decision(session: Session, finding_id: UUID) -> FindingDecision | None:
    return session.scalar(
        select(FindingDecision)
        .where(FindingDecision.finding_id == finding_id)
        .order_by(FindingDecision.review_revision.desc())
        .limit(1)
    )


def finding_dict(session: Session, finding: Finding) -> dict[str, Any]:
    decision = latest_decision(session, finding.id)
    return {
        "id": str(finding.id),
        "rule_id": finding.rule_id,
        "rule_version": finding.rule_version,
        "severity": finding.severity,
        "evidence_ids": finding.evidence_ids,
        "time_range": {"start_ms": finding.start_ms, "end_ms": finding.end_ms}
        if finding.start_ms is not None
        else None,
        "evidence_text": finding.evidence_text,
        "uncertainty": finding.uncertainty,
        "suggested_action": finding.suggested_action,
        "decision": {
            "decision": decision.decision,
            "rationale": decision.rationale,
            "actor_user_id": str(decision.actor_user_id),
            "created_at": decision.created_at,
        }
        if decision
        else None,
    }


def check_dict(session: Session, analysis: Analysis) -> dict[str, Any]:
    evidence = session.scalars(
        select(EvidenceItem)
        .where(EvidenceItem.analysis_id == analysis.id)
        .order_by(EvidenceItem.start_ms)
    ).all()
    findings = session.scalars(
        select(Finding).where(Finding.analysis_id == analysis.id).order_by(Finding.created_at)
    ).all()
    context = session.scalar(select(ReviewContext).where(ReviewContext.analysis_id == analysis.id))
    approval = None
    if context and context.review_status == "approved":
        approval = session.scalar(
            select(Approval)
            .where(
                Approval.review_context_id == context.id,
                Approval.review_revision == context.revision,
            )
            .order_by(Approval.created_at.desc())
            .limit(1)
        )
    version = session.get(SubmissionVersion, analysis.submission_version_id)
    model_calls = session.scalars(
        select(ModelCall)
        .where(ModelCall.analysis_id == analysis.id)
        .order_by(ModelCall.started_at, ModelCall.capability)
    ).all()
    return {
        "id": str(analysis.id),
        "submission_version_id": str(analysis.submission_version_id),
        "submission_version_no": version.version_no if version else None,
        "analysis_status": analysis.analysis_status,
        "machine_assessment": analysis.machine_assessment,
        "review_status": context.review_status if context else "unreviewed",
        "review_version": context.revision if context else None,
        "manifest_hash": analysis.manifest_hash,
        "required_coverage": analysis.required_coverage,
        "observed_coverage": analysis.observed_coverage,
        "missing_intervals": analysis.missing_intervals,
        "invocation_mode": analysis.invocation_mode,
        "scenario": analysis.scenario,
        "prompt_version": analysis.prompt_version,
        "schema_version": analysis.schema_version,
        "model_versions": analysis.model_versions,
        "model_call_summaries": [
            {
                "id": str(call.id),
                "capability": call.capability,
                "attempt_no": call.attempt_no,
                "provider": call.provider,
                "requested_model": call.requested_model,
                "returned_model": call.returned_model,
                "invocation_mode": call.invocation_mode,
                "status": call.status,
                "provider_request_id": call.provider_request_id,
                "usage_units": call.usage_units,
                "cost_known": call.cost_known,
                "cost_minor": call.cost_minor,
                "currency": call.currency,
                "error_code": call.error_code,
                "started_at": call.started_at,
                "completed_at": call.completed_at,
                "live_verified": False,
            }
            for call in model_calls
        ],
        "evidence": [
            {
                "id": str(item.id),
                "modality": item.modality,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "precision": item.precision,
                "description": item.description,
                "captured_at": item.captured_at,
            }
            for item in evidence
        ],
        "findings": [finding_dict(session, item) for item in findings],
        "approval": {
            "id": str(approval.id),
            "reviewer_user_id": str(approval.actor_user_id),
            "created_at": approval.created_at,
            "manifest_hash": approval.manifest_hash,
            "submission_version_id": str(approval.submission_version_id),
            "media_hash": approval.media_hash,
            "caption_hash": approval.caption_hash,
        }
        if approval
        else None,
        "created_at": analysis.created_at,
        "completed_at": analysis.completed_at,
        "limitations": [
            "Fixture execution validates workflow behavior, not live provider capability "
            "or legal compliance."
        ],
    }


def record_finding_decision(
    session: Session,
    principal: Principal,
    finding_id: UUID,
    payload: FindingDecisionCreate,
) -> dict[str, Any]:
    require_roles(principal, "reviewer")
    finding = session.scalar(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.organization_id == principal.organization_id,
        )
    )
    if finding is None:
        raise not_found()
    get_analysis(session, principal, finding.analysis_id, require_authorization=True)
    context = session.scalar(
        select(ReviewContext)
        .where(
            ReviewContext.analysis_id == finding.analysis_id,
            ReviewContext.organization_id == principal.organization_id,
        )
        .with_for_update()
    )
    if context is None:
        raise conflict("REVIEW_NOT_READY", "The review context is not ready.")
    if context.revision != payload.expected_review_version or context.review_status == "superseded":
        raise conflict(
            "REVIEW_CONTEXT_CHANGED", "The review context changed; refresh and try again."
        )
    previous_status = context.review_status
    target_status = (
        "unreviewed" if previous_status in {"approved", "rejected", "revoked"} else previous_status
    )
    _advance_review_context(session, context, payload.expected_review_version, target_status)
    if previous_status == "approved":
        session.add(
            ReviewEvent(
                organization_id=principal.organization_id,
                review_context_id=context.id,
                action="finding_decisions_changed",
                rationale="Finding decisions changed; the previous approval is historical.",
                actor_user_id=principal.user_id,
                review_revision=context.revision,
                manifest_hash=context.manifest_hash,
            )
        )
    decision = FindingDecision(
        organization_id=principal.organization_id,
        finding_id=finding.id,
        review_context_id=context.id,
        decision=payload.decision,
        rationale=payload.rationale,
        actor_user_id=principal.user_id,
        review_revision=context.revision,
    )
    session.add(decision)
    audit(
        session,
        principal,
        "finding.decision_recorded",
        "finding",
        finding.id,
        {"decision": payload.decision, "review_version": context.revision},
    )
    session.commit()
    return {
        "finding_id": str(finding.id),
        "decision": payload.decision,
        "review_version": context.revision,
        "review_status": context.review_status,
    }


def create_fix_request(
    session: Session,
    principal: Principal,
    analysis_id: UUID,
    payload: FixRequestCreate,
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer", "reviewer")
    analysis = get_analysis(session, principal, analysis_id, require_authorization=True)
    query = select(Finding).where(Finding.analysis_id == analysis.id)
    if payload.finding_ids:
        query = query.where(Finding.id.in_(payload.finding_ids))
    findings = session.scalars(query.order_by(Finding.start_ms)).all()
    if payload.finding_ids and len(findings) != len(set(payload.finding_ids)):
        raise not_found()
    if not findings:
        raise unprocessable("NO_FINDINGS_SELECTED", "Select at least one finding for a fix draft.")
    lines = [
        "Please revise this draft. These are reviewer prompts, not a legal certification:",
        *[
            f"- {format_time(item.start_ms)} ({item.rule_id}): {item.suggested_action}"
            for item in findings
        ],
    ]
    draft = FixRequestDraft(
        organization_id=principal.organization_id,
        analysis_id=analysis.id,
        text="\n".join(lines),
        created_by=principal.user_id,
    )
    session.add(draft)
    session.flush()
    audit(session, principal, "fix_request.drafted", "fix_request_draft", draft.id)
    session.commit()
    return {
        "id": str(draft.id),
        "analysis_id": str(analysis.id),
        "text": draft.text,
        "delivery_status": "draft_only",
        "created_at": draft.created_at,
    }


def creator_feedback_dict(
    session: Session,
    feedback: CreatorFeedback,
    *,
    version: SubmissionVersion | None = None,
    submission: Submission | None = None,
) -> dict[str, Any]:
    version = version or session.scalar(
        select(SubmissionVersion).where(
            SubmissionVersion.id == feedback.submission_version_id,
            SubmissionVersion.organization_id == feedback.organization_id,
        )
    )
    submission = submission or session.scalar(
        select(Submission).where(
            Submission.id == feedback.submission_id,
            Submission.organization_id == feedback.organization_id,
        )
    )
    if version is None or submission is None or not feedback.message:
        raise conflict("RESOURCE_DELETED", "The published feedback is no longer available.")
    return {
        "id": str(feedback.id),
        "submission_id": str(feedback.submission_id),
        "submission_version_id": str(feedback.submission_version_id),
        "analysis_id": str(feedback.analysis_id),
        "fix_request_draft_id": str(feedback.fix_request_draft_id),
        "version_no": version.version_no,
        "message": feedback.message,
        "start_ms": feedback.start_ms,
        "end_ms": feedback.end_ms,
        "invocation_mode": feedback.invocation_mode,
        "analysis_status": feedback.analysis_status,
        "manifest_hash": feedback.manifest_hash,
        "published_at": _as_utc(feedback.published_at),
        "historical": submission.current_version_id != version.id,
    }


def publish_creator_feedback(
    session: Session,
    principal: Principal,
    analysis_id: UUID,
    payload: CreatorFeedbackCreate,
    idempotency_key: str | None,
) -> tuple[dict[str, Any], bool]:
    require_roles(principal, "admin", "marketer", "reviewer")
    if not idempotency_key:
        raise bad_request("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required.")
    if len(idempotency_key) > 160:
        raise bad_request("IDEMPOTENCY_KEY_INVALID", "Idempotency-Key is too long.")

    lock_lineage(session, principal.organization_id)
    request_digest = stable_hash(
        {"analysis_id": analysis_id, **payload.model_dump(mode="json")}
    )
    existing = session.scalar(
        select(CreatorFeedback).where(
            CreatorFeedback.organization_id == principal.organization_id,
            CreatorFeedback.published_by_user_id == principal.user_id,
            CreatorFeedback.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_digest != request_digest:
            raise conflict(
                "IDEMPOTENCY_KEY_REUSED",
                "This Idempotency-Key was already used with a different request.",
            )
        existing_version = get_submission_version(
            session, principal, existing.submission_version_id
        )
        existing_submission = _assert_source_available(
            session, principal.organization_id, existing_version
        )
        return creator_feedback_dict(
            session,
            existing,
            version=existing_version,
            submission=existing_submission,
        ), False

    analysis = get_analysis(session, principal, analysis_id, require_authorization=True)
    if analysis.analysis_status not in {"completed", "partial"}:
        raise unprocessable(
            "FEEDBACK_ANALYSIS_NOT_READY",
            "Only completed or partial Check evidence can be shared with a creator.",
        )
    version = get_submission_version(session, principal, analysis.submission_version_id)
    submission = _assert_source_available(session, principal.organization_id, version)
    context = session.scalar(
        select(ReviewContext).where(
            ReviewContext.organization_id == principal.organization_id,
            ReviewContext.analysis_id == analysis.id,
            ReviewContext.submission_id == submission.id,
            ReviewContext.submission_version_id == version.id,
        )
    )
    if (
        submission.current_version_id != version.id
        or context is None
        or context.review_status == "superseded"
    ):
        raise conflict(
            "FEEDBACK_CONTEXT_CHANGED",
            "This Check is no longer the current creator revision context.",
        )
    draft = session.scalar(
        select(FixRequestDraft).where(
            FixRequestDraft.id == payload.fix_request_draft_id,
            FixRequestDraft.organization_id == principal.organization_id,
            FixRequestDraft.analysis_id == analysis.id,
        )
    )
    if draft is None:
        raise not_found()
    asset = session.scalar(
        select(MediaAsset).where(
            MediaAsset.id == version.asset_id,
            MediaAsset.organization_id == principal.organization_id,
            MediaAsset.deleted_at.is_(None),
        )
    )
    if asset is None:
        raise not_found()
    if payload.end_ms is not None and (
        asset.duration_ms is None or payload.end_ms > asset.duration_ms
    ):
        raise unprocessable(
            "FEEDBACK_RANGE_INVALID",
            "The selected feedback timestamps exceed the verified source duration.",
        )

    feedback = CreatorFeedback(
        organization_id=principal.organization_id,
        submission_id=submission.id,
        submission_version_id=version.id,
        analysis_id=analysis.id,
        fix_request_draft_id=draft.id,
        message=payload.message,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        invocation_mode=analysis.invocation_mode,
        analysis_status=analysis.analysis_status,
        manifest_hash=analysis.manifest_hash,
        published_by_user_id=principal.user_id,
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )
    session.add(feedback)
    session.flush()
    audit(
        session,
        principal,
        "creator_feedback.published",
        "creator_feedback",
        feedback.id,
        {
            "analysis_id": str(analysis.id),
            "submission_version_id": str(version.id),
            "invocation_mode": analysis.invocation_mode,
        },
    )
    session.commit()
    return creator_feedback_dict(
        session, feedback, version=version, submission=submission
    ), True


def format_time(milliseconds: int | None) -> str:
    if milliseconds is None:
        return "caption"
    seconds = milliseconds // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _approval_gaps(session: Session, analysis: Analysis) -> list[str]:
    gaps: list[str] = []
    if analysis.analysis_status != "completed":
        gaps.append("analysis_not_complete")
    if set(analysis.required_coverage) - set(analysis.observed_coverage):
        gaps.append("required_evidence_missing")
    findings = session.scalars(select(Finding).where(Finding.analysis_id == analysis.id)).all()
    for finding in findings:
        decision = latest_decision(session, finding.id)
        if decision is None:
            gaps.append(f"finding_unresolved:{finding.id}")
        elif decision.decision not in {"dismissed", "incorrect"}:
            gaps.append(f"finding_blocks_approval:{finding.id}")
    return gaps


def _advance_review_context(
    session: Session, context: ReviewContext, expected_revision: int, target_status: str
) -> None:
    updated = session.execute(
        update(ReviewContext)
        .where(
            ReviewContext.id == context.id,
            ReviewContext.organization_id == context.organization_id,
            ReviewContext.revision == expected_revision,
            ReviewContext.review_status == context.review_status,
        )
        .values(revision=expected_revision + 1, review_status=target_status)
        .returning(ReviewContext.id)
    ).scalar_one_or_none()
    if updated is None:
        raise conflict(
            "REVIEW_CONTEXT_CHANGED", "The review context changed; refresh and try again."
        )
    context.revision = expected_revision + 1
    context.review_status = target_status


def review_decision(
    session: Session,
    principal: Principal,
    analysis_id: UUID,
    payload: ReviewDecisionCreate,
) -> dict[str, Any]:
    require_roles(principal, "reviewer")
    analysis = get_analysis(
        session, principal, analysis_id, require_authorization=payload.action != "revoke"
    )
    context = session.scalar(
        select(ReviewContext)
        .where(
            ReviewContext.analysis_id == analysis.id,
            ReviewContext.organization_id == principal.organization_id,
        )
        .with_for_update()
    )
    if context is None:
        raise conflict("REVIEW_NOT_READY", "The review context is not ready.")
    if context.revision != payload.expected_review_version:
        raise conflict(
            "REVIEW_CONTEXT_CHANGED", "The review context changed; refresh and try again."
        )
    if context.manifest_hash != payload.manifest_hash:
        raise conflict("REVIEW_CONTEXT_CHANGED", "The manifest no longer matches this review.")
    submission = session.get(Submission, context.submission_id)
    if submission is None or submission.current_version_id != context.submission_version_id:
        raise conflict("REVIEW_CONTEXT_CHANGED", "A newer content version requires a new review.")
    if context.review_status == "superseded":
        raise conflict("REVIEW_CONTEXT_CHANGED", "This review was superseded.")

    if payload.action == "approve":
        if context.review_status not in {"unreviewed", "changes_requested"}:
            raise conflict("REVIEW_STATE_CONFLICT", "This review must be reopened before approval.")
        gaps = _approval_gaps(session, analysis)
        if gaps:
            raise unprocessable(
                "REQUIRED_REVIEW_INCOMPLETE",
                f"Approval is blocked: {', '.join(gaps)}.",
            )
        target_status = "approved"
    elif payload.action == "request_changes":
        target_status = "changes_requested"
    elif payload.action == "reject":
        target_status = "rejected"
    else:
        if context.review_status != "approved":
            raise conflict("REVIEW_STATE_CONFLICT", "Only an approved review can be revoked.")
        target_status = "revoked"

    _advance_review_context(session, context, payload.expected_review_version, target_status)
    event = ReviewEvent(
        organization_id=principal.organization_id,
        review_context_id=context.id,
        action=payload.action,
        rationale=payload.rationale,
        actor_user_id=principal.user_id,
        review_revision=context.revision,
        manifest_hash=context.manifest_hash,
    )
    session.add(event)
    if payload.action == "approve":
        version = session.get(SubmissionVersion, context.submission_version_id)
        if version is None:
            raise RuntimeError("review context references a missing version")
        session.add(
            Approval(
                organization_id=principal.organization_id,
                review_context_id=context.id,
                analysis_id=analysis.id,
                submission_version_id=version.id,
                manifest_hash=context.manifest_hash,
                review_revision=context.revision,
                media_hash=version.media_hash,
                caption_hash=version.caption_hash,
                model_versions=analysis.model_versions,
                prompt_version=analysis.prompt_version,
                actor_user_id=principal.user_id,
            )
        )
    audit(
        session,
        principal,
        f"review.{payload.action}",
        "review_context",
        context.id,
        {
            "review_version": context.revision,
            "submission_version_id": str(context.submission_version_id),
        },
    )
    session.commit()
    return {
        "analysis_id": str(analysis.id),
        "review_status": context.review_status,
        "review_version": context.revision,
        "manifest_hash": context.manifest_hash,
        "submission_version_id": str(context.submission_version_id),
        "notice": (
            "This records a human decision for this version; it is not legal "
            "certification or publication."
        ),
    }


def approval_report(
    session: Session,
    principal: Principal,
    analysis_id: UUID,
) -> dict[str, Any]:
    analysis = get_analysis(session, principal, analysis_id)
    context = session.scalar(
        select(ReviewContext).where(
            ReviewContext.analysis_id == analysis.id,
            ReviewContext.organization_id == principal.organization_id,
        )
    )
    if context is None or context.review_status != "approved":
        raise conflict(
            "APPROVAL_REPORT_UNAVAILABLE",
            "A report is available only while this exact version has a current approval.",
        )
    approval = session.scalar(
        select(Approval)
        .where(
            Approval.organization_id == principal.organization_id,
            Approval.review_context_id == context.id,
            Approval.review_revision == context.revision,
            Approval.submission_version_id == context.submission_version_id,
            Approval.manifest_hash == context.manifest_hash,
        )
        .order_by(Approval.created_at.desc())
        .limit(1)
    )
    version = session.get(SubmissionVersion, context.submission_version_id)
    submission = session.get(Submission, context.submission_id)
    if approval is None or version is None or submission is None:
        raise conflict(
            "APPROVAL_REPORT_UNAVAILABLE",
            "The current approval cannot be bound to its immutable source version.",
        )
    campaign = session.scalar(
        select(Campaign).where(
            Campaign.id == submission.campaign_id,
            Campaign.organization_id == principal.organization_id,
        )
    )
    reviewer = session.get(User, approval.actor_user_id)
    event = session.scalar(
        select(ReviewEvent)
        .where(
            ReviewEvent.organization_id == principal.organization_id,
            ReviewEvent.review_context_id == context.id,
            ReviewEvent.review_revision == approval.review_revision,
            ReviewEvent.action == "approve",
        )
        .order_by(ReviewEvent.created_at.desc())
        .limit(1)
    )
    if campaign is None or reviewer is None or event is None:
        raise conflict(
            "APPROVAL_REPORT_UNAVAILABLE",
            "The current approval record is incomplete and cannot be exported.",
        )
    evidence = session.scalars(
        select(EvidenceItem)
        .where(
            EvidenceItem.analysis_id == analysis.id,
            EvidenceItem.organization_id == principal.organization_id,
        )
        .order_by(EvidenceItem.start_ms, EvidenceItem.captured_at)
    ).all()
    findings = session.scalars(
        select(Finding)
        .where(
            Finding.analysis_id == analysis.id,
            Finding.organization_id == principal.organization_id,
        )
        .order_by(Finding.created_at)
    ).all()
    finding_rows: list[dict[str, Any]] = []
    for finding in findings:
        decision = latest_decision(session, finding.id)
        if decision is None or decision.review_context_id != context.id:
            raise conflict(
                "APPROVAL_REPORT_UNAVAILABLE",
                "The approval's finding decisions are incomplete and cannot be exported.",
            )
        finding_rows.append(
            {
                "id": finding.id,
                "rule_id": finding.rule_id,
                "rule_version": finding.rule_version,
                "severity": finding.severity,
                "evidence_ids": [UUID(value) for value in finding.evidence_ids],
                "start_ms": finding.start_ms,
                "end_ms": finding.end_ms,
                "evidence_text": finding.evidence_text,
                "uncertainty": finding.uncertainty,
                "suggested_action": finding.suggested_action,
                "decision": decision.decision,
                "decision_rationale": decision.rationale,
                "decision_actor_user_id": decision.actor_user_id,
                "decided_at": _as_utc(decision.created_at),
            }
        )
    return {
        "report_version": "approval-report.v1",
        "exported_at": utcnow(),
        "current_status": "approved",
        "approval_id": approval.id,
        "analysis_id": analysis.id,
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "submission_version_id": version.id,
        "submission_version_no": version.version_no,
        "rule_pack_version_id": campaign.rule_pack_version_id,
        "manifest_hash": approval.manifest_hash,
        "media_hash": approval.media_hash,
        "caption_hash": approval.caption_hash,
        "reviewer_user_id": reviewer.id,
        "reviewer_display_name": reviewer.display_name,
        "approved_at": _as_utc(approval.created_at),
        "approval_rationale": event.rationale,
        "invocation_mode": analysis.invocation_mode,
        "analysis_status": analysis.analysis_status,
        "schema_version": analysis.schema_version,
        "prompt_version": approval.prompt_version,
        "model_versions": approval.model_versions,
        "required_coverage": analysis.required_coverage,
        "observed_coverage": analysis.observed_coverage,
        "evidence": [
            {
                "id": item.id,
                "modality": item.modality,
                "start_ms": item.start_ms,
                "end_ms": item.end_ms,
                "precision": item.precision,
                "description": item.description,
                "captured_at": _as_utc(item.captured_at),
            }
            for item in evidence
        ],
        "findings": finding_rows,
        "limitations": [
            "This report records a human decision for one immutable content version; "
            "it is not a legal compliance certificate or publication instruction.",
            "Fixture execution validates the Vouch workflow only; it does not establish "
            "live provider capability, provider eligibility, or production quality.",
            "Revocation, source withdrawal, deletion, or a newer content version can make "
            "this approval no longer current.",
        ],
    }


def comparison(
    session: Session,
    principal: Principal,
    analysis_id: UUID,
    previous_analysis_id: UUID,
) -> dict[str, Any]:
    current = get_analysis(session, principal, analysis_id)
    previous = get_analysis(session, principal, previous_analysis_id)
    current_version = session.get(SubmissionVersion, current.submission_version_id)
    previous_version = session.get(SubmissionVersion, previous.submission_version_id)
    if (
        current_version is None
        or previous_version is None
        or current_version.submission_id != previous_version.submission_id
    ):
        raise unprocessable("CHECKS_NOT_COMPARABLE", "Checks must belong to the same submission.")
    current_findings = session.scalars(
        select(Finding).where(Finding.analysis_id == current.id)
    ).all()
    previous_findings = session.scalars(
        select(Finding).where(Finding.analysis_id == previous.id)
    ).all()
    current_map = {item.fingerprint: item for item in current_findings}
    previous_map = {item.fingerprint: item for item in previous_findings}
    compatible = (
        current.model_versions == previous.model_versions
        and current.prompt_version == previous.prompt_version
        and current.schema_version == previous.schema_version
    )
    added = [
        finding_dict(session, current_map[key]) for key in current_map.keys() - previous_map.keys()
    ]
    persisted = [
        finding_dict(session, current_map[key]) for key in current_map.keys() & previous_map.keys()
    ]
    disappeared = previous_map.keys() - current_map.keys()
    if compatible and current.analysis_status == "completed":
        resolved = [finding_dict(session, previous_map[key]) for key in disappeared]
        incomparable: list[dict[str, Any]] = []
    else:
        resolved = []
        incomparable = [finding_dict(session, previous_map[key]) for key in disappeared]
    return {
        "current_check_id": str(current.id),
        "previous_check_id": str(previous.id),
        "compatible_versions": compatible,
        "coverage": {
            "current": current.observed_coverage,
            "previous": previous.observed_coverage,
            "current_missing_intervals": current.missing_intervals,
        },
        "added": added,
        "still_detected": persisted,
        "no_longer_detected": resolved,
        "cannot_compare": incomparable,
        "notice": (
            "Not detected is only treated as no longer detected when versions and "
            "required coverage are compatible."
        ),
    }


def list_audit(session: Session, principal: Principal) -> dict[str, Any]:
    events = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == principal.organization_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(200)
    ).all()
    users = {
        user.id: user
        for user in session.scalars(
            select(User).where(User.id.in_([e.actor_user_id for e in events if e.actor_user_id]))
        ).all()
    }
    return {
        "items": [
            {
                "id": str(event.id),
                "actor_kind": event.actor_kind,
                "actor": {
                    "id": str(event.actor_user_id),
                    "display_name": users[event.actor_user_id].display_name,
                }
                if event.actor_user_id in users
                else {"id": None, "display_name": "Fixture worker"},
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": str(event.resource_id),
                "metadata": event.safe_metadata,
                "created_at": event.created_at,
            }
            for event in events
        ]
    }


def usage(session: Session, principal: Principal) -> dict[str, Any]:
    org = session.get(Organization, principal.organization_id)
    if org is None:
        raise not_found()
    reservations = session.scalars(
        select(BudgetReservation)
        .where(BudgetReservation.organization_id == principal.organization_id)
        .order_by(BudgetReservation.created_at.desc())
    ).all()
    return {
        "currency": org.budget_currency,
        "cap_minor": org.budget_cap_minor,
        "held_minor": org.budget_held_minor,
        "settled_minor": org.budget_settled_minor,
        "fixture_actual_cost_minor": 0,
        "items": [
            {
                "id": str(item.id),
                "job_id": str(item.job_id),
                "held_minor": item.held_minor,
                "settled_minor": item.settled_minor,
                "status": item.status,
            }
            for item in reservations
        ],
    }


def release_reservation(session: Session, job_id: UUID, status: str = "released") -> None:
    reservation = session.scalar(
        select(BudgetReservation).where(BudgetReservation.job_id == job_id).with_for_update()
    )
    if reservation is None or reservation.status != "held":
        return
    org = session.scalar(
        select(Organization).where(Organization.id == reservation.organization_id).with_for_update()
    )
    if org is None:
        raise RuntimeError("budget reservation references a missing organization")
    reservation.status = status
    reservation.reconciled_at = utcnow()
    # Persist the release first so restricted cleanup can prove the resulting held total.
    session.flush([reservation])
    org.budget_held_minor = max(0, org.budget_held_minor - reservation.held_minor)


def get_consent_receipt(
    session: Session, principal: Principal, receipt_id: UUID
) -> ConsentReceipt:
    receipt = session.scalar(
        select(ConsentReceipt).where(
            ConsentReceipt.id == receipt_id,
            ConsentReceipt.organization_id == principal.organization_id,
        )
    )
    if receipt is None:
        raise not_found()
    return receipt


def withdraw_processing_authorization(
    session: Session, principal: Principal, receipt_id: UUID
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    receipt = get_consent_receipt(session, principal, receipt_id)
    deletion = _erase_source(
        session, principal,
        DeletionRequestCreate(resource_type="media_asset", resource_id=receipt.asset_id),
        revocation_reason="withdrawn",
    )
    return _finish_storage_deletion(session, principal, deletion)


def create_deletion_request(
    session: Session,
    principal: Principal,
    payload: DeletionRequestCreate,
) -> dict[str, Any]:
    require_roles(principal, "admin", "marketer")
    deletion = _erase_source(session, principal, payload)
    return _finish_storage_deletion(session, principal, deletion)


def _erase_source(
    session: Session,
    principal: Principal | RetentionActor | GuestPrincipal,
    payload: DeletionRequestCreate,
    *,
    revocation_reason: str | None = None,
) -> DeletionRequest:
    """Shared erasure transaction for members, retention and exact-scope creator guests."""
    is_retention = isinstance(principal, RetentionActor)
    guest_principal = principal if isinstance(principal, GuestPrincipal) else None
    is_guest = guest_principal is not None
    audit_principal = (
        principal if isinstance(principal, (Principal, RetentionActor)) else None
    )
    lock_lineage(session, principal.organization_id)
    if is_retention:
        target = session.scalar(
            select(MediaAsset).where(
                MediaAsset.id == payload.resource_id,
                MediaAsset.organization_id == principal.organization_id,
                MediaAsset.retention_deadline <= utcnow(),
            )
        )
        if payload.resource_type != "media_asset" or target is None:
            raise not_found()
    existing = session.scalar(
        select(DeletionRequest).where(
            DeletionRequest.organization_id == principal.organization_id,
            DeletionRequest.resource_type == payload.resource_type,
            DeletionRequest.resource_id == payload.resource_id,
        )
    )
    if existing is not None:
        return existing
    now = utcnow()
    if payload.resource_type == "submission":
        submission = session.scalar(
            select(Submission).where(
                Submission.id == payload.resource_id,
                Submission.organization_id == principal.organization_id,
            )
        )
        if submission is None:
            raise not_found()
        assets = session.scalars(
            select(MediaAsset).where(
                MediaAsset.organization_id == principal.organization_id,
                MediaAsset.id.in_(
                    select(SubmissionVersion.asset_id).where(
                        SubmissionVersion.organization_id == principal.organization_id,
                        SubmissionVersion.submission_id == submission.id,
                    )
                ),
            )
        ).all()
    else:
        target_asset = session.scalar(
            select(MediaAsset).where(
                MediaAsset.id == payload.resource_id,
                MediaAsset.organization_id == principal.organization_id,
            )
        )
        if target_asset is None:
            raise not_found()
        assets = [target_asset]

    asset_ids = [asset.id for asset in assets]
    versions = session.scalars(
        select(SubmissionVersion).where(
            SubmissionVersion.organization_id == principal.organization_id,
            SubmissionVersion.asset_id.in_(asset_ids),
        )
    ).all()
    affected_submissions = session.scalars(
        select(Submission)
        .where(
            Submission.organization_id == principal.organization_id,
            Submission.id.in_({version.submission_id for version in versions}),
        )
        .order_by(Submission.id)
        .with_for_update()
    ).all()
    for affected_submission in affected_submissions:
        if payload.resource_type == "submission" and affected_submission.id == payload.resource_id:
            affected_submission.deleted_at = now
    assets = session.scalars(
        select(MediaAsset)
        .where(
            MediaAsset.organization_id == principal.organization_id,
            MediaAsset.id.in_(asset_ids),
        )
        .order_by(MediaAsset.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    # Make the durable source-denial visible to scrub-only database policies first.
    for asset in assets:
        asset.filename = ""
        asset.object_bytes = None
        asset.status = "deleted"
        asset.deleted_at = now
    session.flush([*assets, *affected_submissions])
    # Source denial must be visible before the narrowly granted irreversible receipt UPDATE.
    for receipt in session.scalars(
        select(ConsentReceipt).where(
            ConsentReceipt.organization_id == principal.organization_id,
            ConsentReceipt.asset_id.in_(asset_ids),
        )
    ):
        if receipt.revoked_at is None:
            receipt.revoked_at = now
            receipt.revoked_by = None if audit_principal is None else audit_principal.user_id
            receipt.revocation_actor_kind = (
                "retention" if is_retention else "guest" if is_guest else "member"
            )
            receipt.revocation_reason = revocation_reason or (
                "expired" if is_retention else "withdrawn" if is_guest else "source_deleted"
            )
            session.flush([receipt])
            audit(
                session, audit_principal,
                "processing.authorization_revoked", "consent_receipt",
                receipt.id, {"reason": receipt.revocation_reason},
                organization_id=principal.organization_id if is_guest else None,
                actor_guest_session_id=(
                    guest_principal.session_id if guest_principal is not None else None
                ),
            )
    analyses = session.scalars(
        select(Analysis).where(
            Analysis.organization_id == principal.organization_id,
            Analysis.submission_version_id.in_([version.id for version in versions]),
        )
    ).all()
    analysis_ids = [analysis.id for analysis in analyses]
    contexts = session.scalars(
        select(ReviewContext)
        .where(
            ReviewContext.organization_id == principal.organization_id,
            ReviewContext.analysis_id.in_(analysis_ids),
        )
        .order_by(ReviewContext.id)
        .with_for_update()
    ).all()
    jobs = session.scalars(
        select(Job)
        .where(
            Job.organization_id == principal.organization_id,
            Job.resource_id.in_(analysis_ids),
            Job.status.in_(["queued", "running", "retry_wait"]),
        )
        .order_by(Job.id)
        .with_for_update()
    ).all()
    for job in jobs:
        job.status = "cancelled"
        job.fence += 1
        job.lease_owner = None
        job.lease_until = None
        job.retry_after = None
        job.updated_at = now
        if is_retention:
            session.flush([job])
        release_reservation(session, job.id)
    for analysis in analyses:
        if analysis.analysis_status in {"queued", "running"}:
            analysis.analysis_status = "cancelled"
            analysis.completed_at = now
        analysis.machine_assessment = "not_assessed"
        analysis.observed_coverage = []
        analysis.missing_intervals = []
    for context in contexts:
        context.revision += 1
        context.review_status = "revoked"
    for version in versions:
        version.caption = ""
    for asset in assets:
        asset.filename = ""
        asset.object_bytes = None
        asset.status = "deleted"
        asset.deleted_at = now

    # Preserve identifiers/provenance for scoped receipts, but erase retained content and excerpts.
    for evidence in session.scalars(
        select(EvidenceItem).where(
            EvidenceItem.organization_id == principal.organization_id,
            EvidenceItem.analysis_id.in_(analysis_ids),
        )
    ):
        evidence.description = ""
    findings = session.scalars(
        select(Finding).where(
            Finding.organization_id == principal.organization_id,
            Finding.analysis_id.in_(analysis_ids),
        )
    ).all()
    for finding in findings:
        finding.evidence_text = ""
        finding.uncertainty = ""
        finding.suggested_action = ""
    for decision in session.scalars(
        select(FindingDecision).where(
            FindingDecision.organization_id == principal.organization_id,
            FindingDecision.finding_id.in_([finding.id for finding in findings]),
        )
    ):
        decision.rationale = ""
    for event in session.scalars(
        select(ReviewEvent).where(
            ReviewEvent.organization_id == principal.organization_id,
            ReviewEvent.review_context_id.in_([context.id for context in contexts]),
        )
    ):
        event.rationale = ""
    for draft in session.scalars(
        select(FixRequestDraft).where(
            FixRequestDraft.organization_id == principal.organization_id,
            FixRequestDraft.analysis_id.in_(analysis_ids),
        )
    ):
        draft.text = ""
    for feedback in session.scalars(
        select(CreatorFeedback).where(
            CreatorFeedback.organization_id == principal.organization_id,
            CreatorFeedback.analysis_id.in_(analysis_ids),
        )
    ):
        feedback.message = ""
        feedback.start_ms = None
        feedback.end_ms = None
    tombstone = session.scalar(
        select(Tombstone).where(
            Tombstone.organization_id == principal.organization_id,
            Tombstone.resource_type == payload.resource_type,
            Tombstone.resource_id == payload.resource_id,
        )
    )
    if tombstone is None:
        session.add(
            Tombstone(
                organization_id=principal.organization_id,
                resource_type=payload.resource_type,
                resource_id=payload.resource_id,
            )
        )
    remote_asset_ids = [str(asset.id) for asset in assets if asset.storage_backend == "supabase"]
    sandbox_assets = [asset for asset in assets if asset.processing_container]
    has_pending = bool(remote_asset_ids or sandbox_assets)
    deletion = DeletionRequest(
        organization_id=principal.organization_id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        status="partial" if has_pending else "completed",
        destinations=[
            {
                "destination": "local_fixture_database",
                "status": "completed",
                "deleted_artifact_count": len(assets),
                "redacted_version_count": len(versions),
                "redacted_analysis_count": len(analyses),
            },
            {
                "destination": "remote_provider",
                "status": "not_applicable_fixture_mode",
            },
        ]
        + (
            [
                {
                    "destination": "supabase_storage",
                    "status": "pending",
                    "asset_ids": remote_asset_ids,
                }
            ]
            if remote_asset_ids
            else []
        )
        + (
            [{"destination": "local_media_sandbox", "status": "pending",
              "asset_ids": [str(asset.id) for asset in sandbox_assets],
              "container_names": [asset.processing_container for asset in sandbox_assets]}]
            if sandbox_assets else []
        ),
        requested_by=None if audit_principal is None else audit_principal.user_id,
        requested_by_kind="retention" if is_retention else "guest" if is_guest else "member",
        completed_at=None if has_pending else now,
    )
    session.add(deletion)
    session.flush()
    audit(
        session,
        audit_principal,
        "deletion.requested" if has_pending else "deletion.completed",
        "deletion_request",
        deletion.id,
        {"resource_type": payload.resource_type, "resource_id": str(payload.resource_id)},
        organization_id=principal.organization_id if is_guest else None,
        actor_guest_session_id=(
            guest_principal.session_id if guest_principal is not None else None
        ),
    )
    session.commit()
    return deletion


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _claim_deletion(
    session: Session,
    organization_id: UUID,
    deletion_id: UUID,
    *,
    automatic: bool,
    worker_id: str,
) -> DeletionRequest | None:
    # Drop discovery/lineage locks before the independent receipt lease transaction.
    session.commit()
    item = session.scalar(
        select(DeletionRequest)
        .where(
            DeletionRequest.id == deletion_id,
            DeletionRequest.organization_id == organization_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = utcnow()
    if item is None or item.status == "completed":
        return None
    if item.lease_until and _as_utc(item.lease_until) > now:
        return None
    if automatic and (
        item.status == "failed"
        or item.attempt_count >= item.max_attempts
        or (item.retry_after and _as_utc(item.retry_after) > now)
    ):
        # A crash on the last attempt must reach a visible terminal receipt after its lease.
        if item.attempt_count >= item.max_attempts and item.status != "failed":
            item.status = "failed"
            item.last_error_code = "CLEANUP_RETRIES_EXHAUSTED"
            item.lease_owner = None
            item.lease_until = None
            audit(
                session,
                RetentionActor(organization_id),
                "deletion.failed",
                "deletion_request",
                item.id,
                {"attempt": item.attempt_count, "error_code": item.last_error_code},
            )
            session.commit()
        return None
    item.attempt_count += 1
    item.fence += 1
    item.lease_owner = worker_id
    item.lease_until = now + timedelta(seconds=60)
    item.retry_after = None
    item.status = "in_progress"
    session.commit()
    return item


def _finish_storage_deletion(
    session: Session,
    principal: Principal | RetentionActor,
    deletion: DeletionRequest,
    *,
    automatic: bool = False,
    worker_id: str = "member-cleanup",
) -> dict[str, Any]:
    if deletion.status == "completed":
        return deletion_dict(deletion)
    deletion_id = deletion.id
    claimed = _claim_deletion(
        session,
        principal.organization_id,
        deletion_id,
        automatic=automatic,
        worker_id=worker_id,
    )
    if claimed is None:
        current = session.get(DeletionRequest, deletion_id, populate_existing=True)
        if current is None:
            raise not_found()
        return deletion_dict(current)
    deletion = claimed
    fence = claimed.fence
    audit(
        session,
        principal,
        "deletion.attempt_started",
        "deletion_request",
        deletion.id,
        {"attempt": deletion.attempt_count, "automatic": automatic, "fence": fence},
    )
    destinations = [dict(item) for item in deletion.destinations]
    remote = next(
        (item for item in destinations if item["destination"] == "supabase_storage"), None
    )
    sandbox = next(
        (item for item in destinations if item["destination"] == "local_media_sandbox"), None
    )
    remote_ids = [UUID(value) for value in remote["asset_ids"]] if remote else []
    sandbox_ids = [UUID(value) for value in sandbox["asset_ids"]] if sandbox else []
    assets = session.scalars(
        select(MediaAsset).where(
            MediaAsset.organization_id == principal.organization_id,
            MediaAsset.id.in_(set(remote_ids + sandbox_ids)),
            MediaAsset.status == "deleted",
            MediaAsset.deleted_at.is_not(None),
        )
    ).all()
    by_id = {asset.id: asset for asset in assets}
    keys = [by_id[key].object_key for key in remote_ids if key in by_id and by_id[key].object_key]
    # Receipt JSON is not authority for destructive side effects, even with a compromised
    # system DB role. Bind each exact name to a scoped, tombstoned source record first.
    names = [by_id[key].processing_container for key in sandbox_ids if key in by_id]
    sandbox_targets_valid = bool(
        sandbox and len(names) == len(sandbox_ids)
        and all(names) and names == sandbox["container_names"]
    )
    # Tombstones/local erasure commit before any remote side effect. No DB lock spans HTTP.
    session.commit()
    success = bool(remote or sandbox)
    error_code = "STORAGE_CLEANUP_PENDING"
    store: MediaStore | None = session.info.get("media_store")
    if remote is not None and remote["status"] != "completed":
        remote_success = len(keys) == len(remote["asset_ids"]) and store is not None
        for key in keys:
            try:
                if store is not None and key is not None:
                    store.delete(key)
            except ApiError:
                remote_success = False
        remote["status"] = "completed" if remote_success else "retry_pending"
        success = success and remote_success
    if sandbox is not None and sandbox["status"] != "completed":
        sandbox_success = sandbox_targets_valid
        for name in names if sandbox_targets_valid else []:
            try:
                assert name is not None
                remove_sandbox_container(name, principal.organization_id)
            except ApiError:
                sandbox_success = False
        sandbox["status"] = "completed" if sandbox_success else "retry_pending"
        success = success and sandbox_success
        if not sandbox_success:
            error_code = "MEDIA_CLEANUP_PENDING"
    current = session.scalar(
        select(DeletionRequest)
        .where(
            DeletionRequest.id == deletion_id,
            DeletionRequest.organization_id == principal.organization_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if current is None:
        raise not_found()
    if current.status == "completed" or current.fence != fence:
        return deletion_dict(current)
    current.destinations = destinations
    exhausted = automatic and current.attempt_count >= current.max_attempts
    current.status = "completed" if success else "failed" if exhausted else "partial"
    current.completed_at = utcnow() if success else None
    current.lease_owner = None
    current.lease_until = None
    current.last_error_code = None if success else error_code
    current.retry_after = (
        utcnow() + timedelta(seconds=min(300, 2 ** min(current.attempt_count, 8)))
        if not success and not exhausted
        else None
    )
    audit(session, principal, f"deletion.{current.status}", "deletion_request", current.id)
    session.commit()
    return deletion_dict(current)


def read_media(session: Session, principal: Principal, upload_id: UUID) -> tuple[bytes, str]:
    asset = session.scalar(
        select(MediaAsset).where(
            MediaAsset.id == upload_id,
            MediaAsset.organization_id == principal.organization_id,
        )
    )
    if asset is None or asset.deleted_at is not None or asset.status != "validated":
        raise not_found()
    if source_expired(asset):
        raise not_found()
    body: bytes | None
    if asset.storage_backend == "supabase":
        if not principal.access_token or not asset.object_key:
            raise not_found()
        store: MediaStore = session.info["media_store"]
        body = store.download(asset.object_key, principal.access_token)
    else:
        body = asset.object_bytes
    if body is None:
        raise not_found()
    return body, asset.validated_content_type or "application/octet-stream"


def deletion_dict(item: DeletionRequest) -> dict[str, Any]:
    notice = "Source access is blocked; deletion remains incomplete for retry-pending destinations."
    if item.status == "completed":
        if any(d["destination"] == "supabase_storage" for d in item.destinations):
            notice = (
                "Completed covers the declared application database and "
                "private Storage destinations. "
                "No Meta artifact was created in fixture provider mode."
            )
        else:
            notice = (
                "Completed covers the declared local application destinations only; "
                "no provider artifact existed."
            )
    return {
        "id": str(item.id),
        "resource_type": item.resource_type,
        "resource_id": str(item.resource_id),
        "status": item.status,
        "destinations": item.destinations,
        "created_at": item.created_at,
        "completed_at": item.completed_at,
        "requested_by_kind": item.requested_by_kind,
        "attempt_count": item.attempt_count,
        "max_attempts": item.max_attempts,
        "retry_after": item.retry_after,
        "last_error_code": item.last_error_code,
        "notice": notice,
    }


def get_deletion_request(
    session: Session, principal: Principal, deletion_request_id: UUID
) -> dict[str, Any]:
    item = session.scalar(
        select(DeletionRequest).where(
            DeletionRequest.id == deletion_request_id,
            DeletionRequest.organization_id == principal.organization_id,
        )
    )
    if item is None:
        raise not_found()
    return deletion_dict(item)


def list_deletion_requests(
    session: Session,
    principal: Principal,
    campaign_id: UUID | None = None,
) -> dict[str, Any]:
    query = select(DeletionRequest).where(
        DeletionRequest.organization_id == principal.organization_id,
    )
    if campaign_id is not None:
        get_campaign(session, principal, campaign_id)
        asset_ids = select(MediaAsset.id).where(
            MediaAsset.organization_id == principal.organization_id,
            MediaAsset.campaign_id == campaign_id,
        )
        submission_ids = select(Submission.id).where(
            Submission.organization_id == principal.organization_id,
            Submission.campaign_id == campaign_id,
        )
        query = query.where(
            or_(
                (DeletionRequest.resource_type == "media_asset")
                & DeletionRequest.resource_id.in_(asset_ids),
                (DeletionRequest.resource_type == "submission")
                & DeletionRequest.resource_id.in_(submission_ids),
            )
        )
    items = session.scalars(
        query.order_by(DeletionRequest.created_at.desc(), DeletionRequest.id).limit(50),
    ).all()
    return {"items": [deletion_dict(item) for item in items]}
