from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    budget_cap_minor: Mapped[int] = mapped_column(Integer, default=1000)
    budget_held_minor: Mapped[int] = mapped_column(Integer, default=0)
    budget_settled_minor: Mapped[int] = mapped_column(Integer, default=0)
    budget_currency: Mapped[str] = mapped_column(String(3), default="USD")


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(160))
    auth_subject: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, unique=True)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class MembershipRole(Base):
    __tablename__ = "membership_roles"
    __table_args__ = (UniqueConstraint("membership_id", "role"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    membership_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("memberships.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("brands.id"))
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    sku: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1)


class Creator(Base):
    __tablename__ = "creators"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    handle: Mapped[str] = mapped_column(String(160))
    rights_status: Mapped[str] = mapped_column(String(40), default="permission_recorded")
    evidence_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CreatorEvidence(Base):
    __tablename__ = "creator_evidence"
    __table_args__ = (
        CheckConstraint(
            "match_kind in ('exact_product', 'category_relevance')",
            name="ck_creator_evidence_match_kind",
        ),
        CheckConstraint(
            "permission_status in "
            "('permission_recorded', 'license_recorded', 'permission_unknown')",
            name="ck_creator_evidence_permission_status",
        ),
        CheckConstraint(
            "verification_status in ('verified', 'unreviewed', 'unavailable')",
            name="ck_creator_evidence_verification_status",
        ),
        CheckConstraint(
            "evidence_mode in ('human_curated', 'model_analyzed', 'cached')",
            name="ck_creator_evidence_mode",
        ),
        CheckConstraint(
            "source_kind in ('fixture', 'workspace_provided', 'authorized_connector')",
            name="ck_creator_evidence_source_kind",
        ),
        CheckConstraint(
            "match_kind != 'exact_product' or product_id is not null",
            name="ck_creator_evidence_exact_product",
        ),
        ForeignKeyConstraint(
            ["organization_id", "creator_id"],
            ["creators.organization_id", "creators.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
        ),
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint(
            "organization_id",
            "id",
            "creator_id",
            name="uq_creator_evidence_org_id_creator",
        ),
        Index("ix_creator_evidence_org_creator", "organization_id", "creator_id"),
        Index("ix_creator_evidence_org_category", "organization_id", "category"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    creator_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    product_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    category: Mapped[str] = mapped_column(String(80))
    match_kind: Mapped[str] = mapped_column(String(40))
    source_kind: Mapped[str] = mapped_column(String(40))
    source_uri: Mapped[str] = mapped_column(String(500))
    source_label: Mapped[str] = mapped_column(String(160))
    permission_status: Mapped[str] = mapped_column(String(40))
    verification_status: Mapped[str] = mapped_column(String(40))
    evidence_mode: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RulePackVersion(Base):
    __tablename__ = "rule_pack_versions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="draft")
    source_uri: Mapped[str] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64))
    rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class Campaign(Base):
    __tablename__ = "campaigns"
    __table_args__ = (Index("ix_campaign_org_created", "organization_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    objective: Mapped[str] = mapped_column(Text)
    market: Mapped[str] = mapped_column(String(8))
    product_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("products.id"))
    rule_pack_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("rule_pack_versions.id"))
    created_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProductClaim(Base):
    __tablename__ = "product_claims"
    __table_args__ = (
        CheckConstraint("status IN ('approved', 'withdrawn')"),
        ForeignKeyConstraint(
            ["organization_id", "product_id"],
            ["products.organization_id", "products.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("organization_id", "id"),
        Index("ix_product_claims_product", "organization_id", "product_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    approved_wording: Mapped[str] = mapped_column(Text)
    evidence_label: Mapped[str] = mapped_column(String(160))
    evidence_uri: Mapped[str] = mapped_column(String(500))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="approved")
    created_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CampaignRequirement(Base):
    __tablename__ = "campaign_requirements"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('disclosure', 'product_visibility', 'cta', 'exact_phrase', "
            "'approved_claim')"
        ),
        ForeignKeyConstraint(
            ["organization_id", "campaign_id"],
            ["campaigns.organization_id", "campaigns.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "claim_id"],
            ["product_claims.organization_id", "product_claims.id"],
        ),
        UniqueConstraint("organization_id", "id"),
        Index(
            "ix_campaign_requirements_campaign",
            "organization_id",
            "campaign_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    kind: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(160))
    expected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CampaignCreator(Base):
    __tablename__ = "campaign_creators"
    __table_args__ = (
        UniqueConstraint("campaign_id", "creator_id"),
        UniqueConstraint("organization_id", "campaign_id", "creator_id"),
        ForeignKeyConstraint(
            ["organization_id", "evidence_id", "creator_id"],
            [
                "creator_evidence.organization_id",
                "creator_evidence.id",
                "creator_evidence.creator_id",
            ],
            name="fk_campaign_creator_evidence_scope",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    creator_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("creators.id"))
    evidence_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)


class OutcomeEvent(Base):
    __tablename__ = "outcome_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "environment", "external_event_id"),
        CheckConstraint("event_kind IN ('click', 'order', 'refund')"),
        CheckConstraint("environment IN ('test', 'live')"),
        CheckConstraint("amount_minor >= 0"),
        CheckConstraint("length(currency) = 3"),
        CheckConstraint("length(payload_hash) = 64"),
        Index("ix_outcome_campaign_received", "organization_id", "campaign_id", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    creator_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("creators.id"), index=True)
    event_kind: Mapped[str] = mapped_column(String(16))
    environment: Mapped[str] = mapped_column(String(8), default="test")
    external_event_id: Mapped[str] = mapped_column(String(160))
    order_external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    amount_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    attribution_status: Mapped[str] = mapped_column(String(24), default="attributed")
    attribution_method: Mapped[str] = mapped_column(String(40), default="test_roster")
    payload_hash: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MediaAsset(Base):
    __tablename__ = "media_assets"
    __table_args__ = (
        CheckConstraint(
            "(uploader_user_id IS NOT NULL AND uploader_guest_session_id IS NULL) OR "
            "(uploader_user_id IS NULL AND uploader_guest_session_id IS NOT NULL)",
            name="ck_media_asset_uploader_xor",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            "uploader_user_id",
            name="uq_media_asset_member_uploader",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            "uploader_guest_session_id",
            name="uq_media_asset_guest_uploader",
        ),
        ForeignKeyConstraint(
            ["organization_id", "uploader_guest_session_id"],
            ["guest_sessions.organization_id", "guest_sessions.id"],
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("campaigns.id"), index=True)
    uploader_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    uploader_guest_session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    proposed_content_type: Mapped[str] = mapped_column(String(100))
    validated_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_bytes: Mapped[int] = mapped_column(Integer)
    actual_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default="{}"
    )
    status: Mapped[str] = mapped_column(String(32), default="intent_created")
    upload_token_hash: Mapped[str] = mapped_column(String(64))
    finalize_token_hash: Mapped[str] = mapped_column(String(64))
    object_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    storage_backend: Mapped[str] = mapped_column(
        String(32), default="database", server_default="database"
    )
    object_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    processing_container: Mapped[str | None] = mapped_column(String(160), nullable=True)
    processing_lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rights_attested: Mapped[bool] = mapped_column(Boolean)
    retention_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", "campaign_id", "creator_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("campaigns.id"), index=True)
    creator_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("creators.id"))
    current_version_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SubmissionVersion(Base):
    __tablename__ = "submission_versions"
    __table_args__ = (
        UniqueConstraint("submission_id", "version_no"),
        CheckConstraint(
            "(uploader_user_id IS NOT NULL AND uploader_guest_session_id IS NULL) OR "
            "(uploader_user_id IS NULL AND uploader_guest_session_id IS NOT NULL)",
            name="ck_submission_version_uploader_xor",
        ),
        ForeignKeyConstraint(
            ["organization_id", "uploader_guest_session_id"],
            ["guest_sessions.organization_id", "guest_sessions.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "asset_id", "uploader_user_id"],
            [
                "media_assets.organization_id",
                "media_assets.id",
                "media_assets.uploader_user_id",
            ],
            name="fk_submission_version_member_uploader",
        ),
        ForeignKeyConstraint(
            ["organization_id", "asset_id", "uploader_guest_session_id"],
            [
                "media_assets.organization_id",
                "media_assets.id",
                "media_assets.uploader_guest_session_id",
            ],
            name="fk_submission_version_guest_uploader",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    submission_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("submissions.id", ondelete="CASCADE"), index=True
    )
    version_no: Mapped[int] = mapped_column(Integer)
    asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("media_assets.id"))
    media_hash: Mapped[str] = mapped_column(String(64))
    caption: Mapped[str] = mapped_column(Text)
    caption_hash: Mapped[str] = mapped_column(String(64))
    uploader_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    uploader_guest_session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    rights_attested: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GuestGrant(Base):
    __tablename__ = "guest_grants"
    __table_args__ = (
        UniqueConstraint("invitation_secret_hash"),
        UniqueConstraint(
            "organization_id",
            "id",
            "campaign_id",
            "creator_id",
            "submission_id",
            "issued_by_user_id",
            "issuance_recovery_id",
            name="uq_guest_grant_renewal_root_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "campaign_id", "creator_id"],
            [
                "campaign_creators.organization_id",
                "campaign_creators.campaign_id",
                "campaign_creators.creator_id",
            ],
        ),
        ForeignKeyConstraint(
            ["organization_id", "submission_id", "campaign_id", "creator_id"],
            [
                "submissions.organization_id",
                "submissions.id",
                "submissions.campaign_id",
                "submissions.creator_id",
            ],
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "renewal_root_id",
                "campaign_id",
                "creator_id",
                "submission_id",
                "issued_by_user_id",
                "issuance_recovery_id",
            ],
            [
                "guest_grants.organization_id",
                "guest_grants.id",
                "guest_grants.campaign_id",
                "guest_grants.creator_id",
                "guest_grants.submission_id",
                "guest_grants.issued_by_user_id",
                "guest_grants.issuance_recovery_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("source_count >= 0 AND source_count <= 5"),
        CheckConstraint("reserved_bytes >= 0 AND reserved_bytes <= 25000000"),
        Index("ix_guest_grant_expiry", "expires_at", "revoked_at"),
        Index(
            "ix_guest_grant_recovery",
            "organization_id",
            "issued_by_user_id",
            "issuance_recovery_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    creator_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("creators.id"))
    submission_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("submissions.id", ondelete="CASCADE"), index=True
    )
    issued_by_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    issuance_recovery_id: Mapped[UUID] = mapped_column(Uuid)
    renewal_root_id: Mapped[UUID] = mapped_column(Uuid)
    scope_kind: Mapped[str] = mapped_column(String(32))
    invitation_secret_hash: Mapped[str] = mapped_column(String(64))
    allowed_actions: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: ["read_submission", "upload_source", "submit_version"],
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reserved_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GuestSession(Base):
    __tablename__ = "guest_sessions"
    __table_args__ = (
        UniqueConstraint("grant_id"),
        UniqueConstraint("session_secret_hash"),
        Index("ix_guest_session_expiry", "expires_at", "revoked_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    grant_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("guest_grants.id", ondelete="CASCADE"), index=True
    )
    session_secret_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GuestCommand(Base):
    __tablename__ = "guest_commands"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "guest_session_id",
            "operation",
            "idempotency_key",
            name="uq_guest_command_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "guest_session_id"],
            ["guest_sessions.organization_id", "guest_sessions.id"],
            ondelete="CASCADE",
        ),
        CheckConstraint(
            "operation IN ('guest_upload_intent', 'guest_submission_version')",
            name="ck_guest_command_operation",
        ),
        CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 160",
            name="ck_guest_command_key",
        ),
        CheckConstraint("length(request_digest) = 64", name="ck_guest_command_digest"),
        CheckConstraint(
            "(operation = 'guest_upload_intent' "
            "AND result_resource_type = 'media_asset') OR "
            "(operation = 'guest_submission_version' "
            "AND result_resource_type = 'submission_version')",
            name="ck_guest_command_result_mapping",
        ),
        Index("ix_guest_command_session_created", "guest_session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    guest_session_id: Mapped[UUID] = mapped_column(Uuid)
    operation: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_digest: Mapped[str] = mapped_column(String(64))
    result_resource_type: Mapped[str] = mapped_column(String(40))
    result_resource_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GuestExchangeAttempt(Base):
    __tablename__ = "guest_exchange_attempts"
    __table_args__ = (
        Index("ix_guest_exchange_attempt_expiry", "attempted_at"),
        Index("ix_guest_exchange_client_window", "client_bucket_hash", "attempted_at"),
        Index("ix_guest_exchange_token_window", "token_digest", "attempted_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    client_bucket_hash: Mapped[str] = mapped_column(String(64))
    token_digest: Mapped[str] = mapped_column(String(64))
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("job_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    submission_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("submission_versions.id"), index=True
    )
    job_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(32), default="queued")
    machine_assessment: Mapped[str] = mapped_column(String(40), default="not_assessed")
    manifest_hash: Mapped[str] = mapped_column(String(64))
    invocation_mode: Mapped[str] = mapped_column(String(16), default="fixture")
    scenario: Mapped[str] = mapped_column(String(40))
    required_coverage: Mapped[list[str]] = mapped_column(JSON)
    observed_coverage: Mapped[list[str]] = mapped_column(JSON, default=list)
    missing_intervals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    model_versions: Mapped[dict[str, str]] = mapped_column(JSON)
    prompt_version: Mapped[str] = mapped_column(String(40))
    schema_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    modality: Mapped[str] = mapped_column(String(32))
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    precision: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    rule_id: Mapped[str] = mapped_column(String(100))
    rule_version: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(16))
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text)
    uncertainty: Mapped[str] = mapped_column(String(80))
    suggested_action: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewContext(Base):
    __tablename__ = "review_contexts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), unique=True
    )
    submission_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("submissions.id"), index=True)
    submission_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("submission_versions.id"))
    review_status: Mapped[str] = mapped_column(String(32), default="unreviewed")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FindingDecision(Base):
    __tablename__ = "finding_decisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    finding_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("findings.id"), index=True)
    review_context_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("review_contexts.id"))
    decision: Mapped[str] = mapped_column(String(24))
    rationale: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    review_revision: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReviewEvent(Base):
    __tablename__ = "review_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    review_context_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("review_contexts.id"))
    action: Mapped[str] = mapped_column(String(32))
    rationale: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    review_revision: Mapped[int] = mapped_column(Integer)
    manifest_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    review_context_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("review_contexts.id"))
    analysis_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("analyses.id"))
    submission_version_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("submission_versions.id"))
    manifest_hash: Mapped[str] = mapped_column(String(64))
    review_revision: Mapped[int] = mapped_column(Integer)
    media_hash: Mapped[str] = mapped_column(String(64))
    caption_hash: Mapped[str] = mapped_column(String(64))
    model_versions: Mapped[dict[str, str]] = mapped_column(JSON)
    prompt_version: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FixRequestDraft(Base):
    __tablename__ = "fix_request_drafts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("analyses.id"))
    text: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CreatorFeedback(Base):
    __tablename__ = "creator_feedback"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "published_by_user_id",
            "idempotency_key",
            name="uq_creator_feedback_actor_idempotency",
        ),
        CheckConstraint(
            "(start_ms IS NULL AND end_ms IS NULL) OR "
            "(start_ms IS NOT NULL AND start_ms >= 0 AND end_ms > start_ms)",
            name="ck_creator_feedback_time_range",
        ),
        Index("ix_creator_feedback_submission_published", "submission_id", "published_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    submission_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("submissions.id", ondelete="CASCADE"), index=True
    )
    submission_version_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("submission_versions.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    fix_request_draft_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("fix_request_drafts.id", ondelete="CASCADE")
    )
    message: Mapped[str] = mapped_column(Text)
    start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    invocation_mode: Mapped[str] = mapped_column(String(16))
    analysis_status: Mapped[str] = mapped_column(String(32))
    manifest_hash: Mapped[str] = mapped_column(String(64))
    published_by_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    idempotency_key: Mapped[str] = mapped_column(String(160))
    request_digest: Mapped[str] = mapped_column(String(64))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_job_claim", "status", "retry_after", "lease_until"),
        UniqueConstraint("organization_id", "logical_key"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40), default="check")
    resource_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    logical_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fence: Mapped[int] = mapped_column(Integer, default=0)
    scenario: Mapped[str] = mapped_column(String(40))
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    result_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("organization_id", "actor_user_id", "operation", "key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(80))
    key: Mapped[str] = mapped_column(String(160))
    request_hash: Mapped[str] = mapped_column(String(64))
    job_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("jobs.id"))
    resource_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BudgetReservation(Base):
    __tablename__ = "budget_reservations"
    __table_args__ = (UniqueConstraint("organization_id", "logical_key"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    job_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("jobs.id"), unique=True)
    logical_key: Mapped[str] = mapped_column(String(128))
    held_minor: Mapped[int] = mapped_column(Integer)
    settled_minor: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[str] = mapped_column(String(24), default="held")
    price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelCall(Base):
    __tablename__ = "model_calls"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "job_id", "attempt_no", "capability",
            name="uq_model_call_job_attempt_capability",
        ),
        CheckConstraint(
            "(cost_known AND cost_minor IS NOT NULL) OR "
            "(NOT cost_known AND cost_minor IS NULL)",
            name="ck_model_call_cost_known",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    analysis_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("analyses.id", ondelete="CASCADE"), index=True
    )
    budget_reservation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("budget_reservations.id"), index=True
    )
    logical_operation_key: Mapped[str] = mapped_column(String(220))
    capability: Mapped[str] = mapped_column(String(40))
    attempt_no: Mapped[int] = mapped_column(Integer)
    invocation_mode: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    requested_model: Mapped[str] = mapped_column(String(160))
    returned_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(80))
    schema_version: Mapped[str] = mapped_column(String(80))
    adapter_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="requested")
    provider_request_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    usage_units: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cost_known: Mapped[bool] = mapped_column(Boolean, default=True)
    cost_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(
            "(actor_kind = 'guest' AND actor_user_id IS NULL "
            "AND actor_guest_session_id IS NOT NULL) OR "
            "(actor_kind <> 'guest' AND actor_guest_session_id IS NULL)",
            name="ck_audit_event_guest_actor",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_guest_session_id"],
            ["guest_sessions.organization_id", "guest_sessions.id"],
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    actor_guest_session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    actor_kind: Mapped[str] = mapped_column(String(24))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[UUID] = mapped_column(Uuid)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Tombstone(Base):
    __tablename__ = "tombstones"
    __table_args__ = (UniqueConstraint("organization_id", "resource_type", "resource_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeletionRequest(Base):
    __tablename__ = "deletion_requests"
    __table_args__ = (Index("ix_deletion_request_claim", "status", "retry_after", "lease_until"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(24), default="requested")
    destinations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    requested_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    requested_by_kind: Mapped[str] = mapped_column(
        String(24), default="member", server_default="member"
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentReceipt(Base):
    __tablename__ = "consent_receipts"
    __table_args__ = (
        CheckConstraint(
            "(actor_user_id IS NOT NULL AND actor_guest_session_id IS NULL) OR "
            "(actor_user_id IS NULL AND actor_guest_session_id IS NOT NULL)",
            name="ck_consent_receipt_actor_xor",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_guest_session_id"],
            ["guest_sessions.organization_id", "guest_sessions.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "asset_id", "actor_user_id"],
            [
                "media_assets.organization_id",
                "media_assets.id",
                "media_assets.uploader_user_id",
            ],
            name="fk_consent_receipt_member_uploader",
        ),
        ForeignKeyConstraint(
            ["organization_id", "asset_id", "actor_guest_session_id"],
            [
                "media_assets.organization_id",
                "media_assets.id",
                "media_assets.uploader_guest_session_id",
            ],
            name="fk_consent_receipt_guest_uploader",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), index=True
    )
    asset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("media_assets.id"), unique=True)
    campaign_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("campaigns.id"))
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    actor_guest_session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    purpose: Mapped[str] = mapped_column(String(40))
    notice_version: Mapped[str] = mapped_column(String(80))
    notice_hash: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), nullable=True)
    revocation_actor_kind: Mapped[str | None] = mapped_column(String(24), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)


# Tenant references are composite even when UUIDs happen to be globally unique.
# Keep this in metadata so SQLite proofs and generated PostgreSQL DDL share the guard.
for tenant_table in Base.metadata.tables.values():
    if "organization_id" not in tenant_table.c:
        continue
    tenant_table.append_constraint(UniqueConstraint("organization_id", "id"))
    for reference in list(tenant_table.foreign_keys):
        constraint = reference.constraint
        if constraint is not None and any(
            element.parent.name == "organization_id" for element in constraint.elements
        ):
            # Explicit multi-column tenant/lineage constraints already carry their
            # organization source. Adding another generic pair would duplicate it.
            continue
        parent_table = reference.column.table
        if "organization_id" not in parent_table.c:
            continue
        tenant_table.append_constraint(
            ForeignKeyConstraint(
                ["organization_id", reference.parent.name],
                [f"{parent_table.name}.organization_id", reference.target_fullname],
            )
        )
