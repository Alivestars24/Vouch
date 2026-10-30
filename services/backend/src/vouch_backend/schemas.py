from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StorageUsageResponse(ApiModel):
    limit_bytes: int = Field(ge=0)
    used_bytes: int = Field(ge=0)
    reserved_bytes: int = Field(ge=0)
    pending_cleanup_bytes: int = Field(ge=0)
    available_bytes: int = Field(ge=0)
    max_upload_bytes: int = Field(gt=0)
    storage_backend: Literal["database", "supabase"]


class ConsentReceiptRead(ApiModel):
    id: UUID
    asset_id: UUID
    campaign_id: UUID
    actor_user_id: UUID | None
    actor_guest_session_id: UUID | None
    purpose: Literal["campaign_check"]
    notice_version: str = Field(min_length=1, max_length=80)
    notice_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    accepted_at: AwareDatetime = Field(description="Authorization acknowledgment time in UTC.")
    revoked_at: AwareDatetime | None = Field(description="Irreversible revocation time in UTC.")
    revoked_by: UUID | None
    revocation_actor_kind: Literal["member", "retention"] | None
    revocation_reason: Literal["withdrawn", "source_deleted", "expired"] | None

    @model_validator(mode="after")
    def actor_is_exactly_one_identity(self) -> ConsentReceiptRead:
        if (self.actor_user_id is None) == (self.actor_guest_session_id is None):
            raise ValueError("receipt actor must be exactly one member or guest session")
        return self

    @field_validator("accepted_at", "revoked_at")
    @classmethod
    def timestamps_are_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() != timedelta(0):
            raise ValueError("receipt timestamps must be UTC")
        return value


class CampaignCreate(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1, max_length=2000)
    market: str = Field(min_length=2, max_length=8)
    product_id: UUID
    rule_pack_version_id: UUID
    creator_ids: list[UUID] = Field(default_factory=list, max_length=20)


class ProductClaimCreate(ApiModel):
    approved_wording: str = Field(min_length=1, max_length=2000)
    evidence_label: str = Field(min_length=1, max_length=160)
    evidence_uri: str = Field(min_length=1, max_length=500)
    expires_at: AwareDatetime | None = None


class ProductClaimRead(ApiModel):
    id: UUID
    product_id: UUID
    approved_wording: str
    evidence_label: str
    evidence_uri: str
    expires_at: AwareDatetime | None
    status: Literal["approved", "expired", "withdrawn"]
    created_at: AwareDatetime


RequirementKind = Literal[
    "disclosure", "product_visibility", "cta", "exact_phrase", "approved_claim"
]


class CampaignRequirementCreate(ApiModel):
    kind: RequirementKind
    label: str = Field(min_length=1, max_length=160)
    expected_text: str | None = Field(default=None, min_length=1, max_length=2000)
    claim_id: UUID | None = None
    required: bool = True

    @model_validator(mode="after")
    def reference_matches_kind(self) -> CampaignRequirementCreate:
        if self.kind == "approved_claim" and self.claim_id is None:
            raise ValueError("approved claim requirements need claim_id")
        if self.kind != "approved_claim" and self.claim_id is not None:
            raise ValueError("claim_id is only valid for approved claim requirements")
        if self.kind in {"cta", "exact_phrase"} and self.expected_text is None:
            raise ValueError("text requirements need expected_text")
        return self


class CampaignRequirementRead(ApiModel):
    id: UUID
    campaign_id: UUID
    kind: RequirementKind
    label: str
    expected_text: str | None
    claim_id: UUID | None
    required: bool
    created_at: AwareDatetime


class BriefRequirementAssessmentRead(ApiModel):
    requirement_id: UUID
    submission_id: UUID | None
    submission_version_id: UUID | None
    analysis_id: UUID | None
    status: Literal["observed", "missing", "unknown"]
    detail: str
    evidence_ids: list[UUID]


class CampaignBriefRead(ApiModel):
    campaign_id: UUID
    claims: list[ProductClaimRead]
    requirements: list[CampaignRequirementRead]
    assessments: list[BriefRequirementAssessmentRead]
    limitations: list[str]


class TestOutcomeEventCreate(ApiModel):
    creator_id: UUID
    event_kind: Literal["click", "order", "refund"]
    external_event_id: str = Field(min_length=1, max_length=160)
    order_external_id: str | None = Field(default=None, min_length=1, max_length=160)
    amount_minor: int = Field(default=0, ge=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    occurred_at: AwareDatetime

    @model_validator(mode="after")
    def event_shape_matches_kind(self) -> TestOutcomeEventCreate:
        if self.event_kind == "click" and (
            self.order_external_id is not None or self.amount_minor != 0
        ):
            raise ValueError("click events cannot carry order value")
        if self.event_kind in {"order", "refund"} and self.order_external_id is None:
            raise ValueError("order and refund events require order_external_id")
        if self.event_kind == "refund" and self.amount_minor == 0:
            raise ValueError("refund amount must be greater than zero")
        return self


class OutcomeEventRead(ApiModel):
    id: UUID
    creator_id: UUID
    event_kind: Literal["click", "order", "refund"]
    environment: Literal["test", "live"]
    external_event_id: str
    order_external_id: str | None
    amount_minor: int = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    attribution_status: Literal["attributed", "ambiguous", "unattributed"]
    attribution_method: str
    occurred_at: AwareDatetime
    received_at: AwareDatetime


class TrackEnvironmentSummary(ApiModel):
    clicks: int = Field(ge=0)
    orders: int = Field(ge=0)
    refunds: int = Field(ge=0)
    conversion_rate: float | None = Field(default=None, ge=0)
    totals_by_currency: dict[str, dict[str, int]]


class CampaignTrackRead(ApiModel):
    campaign_id: UUID
    freshness_at: AwareDatetime | None
    test: TrackEnvironmentSummary
    live: TrackEnvironmentSummary
    events: list[OutcomeEventRead]


ReadinessSeverity = Literal["blocker", "action", "ready"]
ReadinessCategory = Literal["upload", "check", "evidence", "review", "cleanup"]
ReadinessSourceType = Literal[
    "campaign", "submission", "submission_version", "analysis", "review_context", "deletion_request"
]


class ReadinessCitationRead(ApiModel):
    source_type: ReadinessSourceType
    source_id: UUID
    label: str
    href: str


class ReadinessItemRead(ApiModel):
    id: str
    severity: ReadinessSeverity
    category: ReadinessCategory
    title: str
    detail: str
    action_label: str
    citation: ReadinessCitationRead


class CampaignReadinessRead(ApiModel):
    campaign_id: UUID
    generation_mode: Literal["deterministic_records"]
    ready: bool
    blocker_count: int = Field(ge=0)
    action_count: int = Field(ge=0)
    summary: str
    items: list[ReadinessItemRead]
    limitations: list[str]


CreatorMatchKind = Literal["exact_product", "category_relevance"]
CreatorPermissionStatus = Literal[
    "permission_recorded", "license_recorded", "permission_unknown"
]
CreatorVerificationStatus = Literal["verified", "unreviewed", "unavailable"]
CreatorEvidenceMode = Literal["human_curated", "model_analyzed", "cached"]
CreatorEvidenceSourceKind = Literal["fixture", "workspace_provided", "authorized_connector"]


class CreatorEvidenceRead(ApiModel):
    id: UUID
    product_id: UUID | None
    category: str
    match_kind: CreatorMatchKind
    source_kind: CreatorEvidenceSourceKind
    source_uri: str
    source_label: str
    permission_status: CreatorPermissionStatus
    verification_status: CreatorVerificationStatus
    evidence_mode: CreatorEvidenceMode
    description: str
    captured_at: datetime


class CreatorCatalogRead(ApiModel):
    id: UUID
    name: str
    handle: str
    rights_status: str
    evidence_timestamp: datetime
    evidence: list[CreatorEvidenceRead]


class CreatorCatalogResponse(ApiModel):
    collection: Literal["curated"]
    items: list[CreatorCatalogRead]


class CampaignCreatorCreate(ApiModel):
    creator_id: UUID
    evidence_id: UUID


class CampaignCreatorRead(ApiModel):
    id: UUID
    campaign_id: UUID
    creator_id: UUID
    evidence_id: UUID
    created: bool


class UploadIntentCreate(ApiModel):
    campaign_id: UUID
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["video/mp4", "video/webm"]
    byte_size: int = Field(gt=0, le=5_000_000)
    rights_attested: bool
    notice_version: str = Field(min_length=1, max_length=80)
    notice_acknowledged: Literal[True]
    purpose: Literal["campaign_check"]

    @field_validator("notice_acknowledged", mode="before")
    @classmethod
    def affirmative_notice_required(cls, value: object) -> object:
        if value is not True:
            raise ValueError("processing notice must be affirmatively acknowledged")
        return value

    @field_validator("rights_attested")
    @classmethod
    def rights_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("content rights must be attested before upload")
        return value


class UploadFinalize(ApiModel):
    finalize_token: str = Field(min_length=20, max_length=500)


class SubmissionCreate(ApiModel):
    asset_id: UUID
    creator_id: UUID
    caption: str = Field(max_length=10_000)
    rights_attested: bool


class SubmissionVersionCreate(ApiModel):
    asset_id: UUID
    caption: str = Field(max_length=10_000)
    rights_attested: bool


class GuestInvitationCreate(ApiModel):
    creator_id: UUID
    submission_id: UUID | None = None
    recovery_id: UUID


class GuestInvitationRead(ApiModel):
    id: UUID
    campaign_id: UUID
    creator_id: UUID
    submission_id: UUID
    allowed_actions: list[Literal["read_submission", "upload_source", "submit_version"]]
    expires_at: AwareDatetime
    invitation_url: str


class GuestExchangeCreate(ApiModel):
    invitation_secret: str = Field(min_length=1, max_length=500)


class GuestExchangeRead(ApiModel):
    status: Literal["active"]
    expires_at: AwareDatetime


class GuestCampaignRead(ApiModel):
    name: str
    market: str
    brand_name: str


class GuestCreatorRead(ApiModel):
    name: str
    handle: str


class GuestCurrentVersionRead(ApiModel):
    id: UUID
    version_no: int = Field(ge=1)
    caption: str
    created_at: AwareDatetime
    consent_receipt_id: UUID | None = None


class GuestSubmissionSummaryRead(ApiModel):
    current_version: GuestCurrentVersionRead | None
    review_state: Literal["awaiting_brand_review", "changes_requested", "approved"]
    approved_version_no: int | None = Field(default=None, ge=1)


class GuestFeedbackRead(ApiModel):
    version_no: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=2000)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    invocation_mode: Literal["fixture", "recorded", "live"]
    analysis_status: Literal["queued", "running", "completed", "partial", "failed", "cancelled"]
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    published_at: AwareDatetime
    historical: bool


class GuestSubmissionRead(ApiModel):
    session_expires_at: AwareDatetime
    campaign: GuestCampaignRead
    creator: GuestCreatorRead
    submission: GuestSubmissionSummaryRead
    allowed_actions: list[Literal["read_submission", "upload_source", "submit_version"]]
    feedback: list[GuestFeedbackRead]


class GuestConsentReceiptRead(ApiModel):
    id: UUID
    purpose: Literal["campaign_check"]
    notice_version: str = Field(min_length=1, max_length=80)
    notice_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    accepted_at: AwareDatetime


class GuestUploadIntentCreate(ApiModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["video/mp4", "video/webm"]
    byte_size: int = Field(gt=0, le=5_000_000)
    rights_attested: bool
    notice_version: str = Field(min_length=1, max_length=80)
    notice_acknowledged: Literal[True]
    purpose: Literal["campaign_check"]

    @field_validator("notice_acknowledged", mode="before")
    @classmethod
    def affirmative_notice_required(cls, value: object) -> object:
        if value is not True:
            raise ValueError("processing notice must be affirmatively acknowledged")
        return value

    @field_validator("rights_attested")
    @classmethod
    def rights_required(cls, value: bool) -> bool:
        if not value:
            raise ValueError("content rights must be attested before upload")
        return value


class GuestUploadIntentRead(ApiModel):
    upload_id: UUID
    content_url: str
    upload_token: str = Field(min_length=20)
    finalize_url: str
    finalize_token: str = Field(min_length=20)
    required_header: Literal["X-Upload-Token"]
    max_bytes: int = Field(gt=0)
    expires_at: AwareDatetime
    authorization_status: Literal["active"]
    consent_receipt: GuestConsentReceiptRead


class GuestUploadContentRead(ApiModel):
    upload_id: UUID
    status: Literal["content_uploaded"]
    received_bytes: int = Field(gt=0, le=5_000_000)


class GuestUploadFinalize(ApiModel):
    finalize_token: str = Field(min_length=20, max_length=500)


class GuestMediaAssetRead(ApiModel):
    asset_id: UUID
    status: Literal["validated"]


class GuestSubmissionVersionCreate(ApiModel):
    asset_id: UUID
    caption: str = Field(max_length=10_000)
    expected_current_version_id: UUID | None


class GuestSubmissionVersionRead(ApiModel):
    id: UUID
    version_no: int = Field(ge=1)
    caption: str = Field(max_length=10_000)
    created_at: AwareDatetime


FixtureScenario = Literal[
    "success",
    "clean",
    "partial_voice",
    "transient_then_success",
    "invalid_output",
    "provider_down",
]


class CheckCreate(ApiModel):
    scenario: FixtureScenario = "success"
    invocation_mode: Literal["fixture"] = "fixture"
    schema_version: Literal["check-result.v1"] = "check-result.v1"


class FindingDecisionCreate(ApiModel):
    decision: Literal["accepted", "dismissed", "incorrect", "uncertain"]
    rationale: str = Field(min_length=3, max_length=2000)
    expected_review_version: int = Field(ge=1)


class ReviewDecisionCreate(ApiModel):
    action: Literal["approve", "reject", "request_changes", "revoke"]
    expected_review_version: int = Field(ge=1)
    manifest_hash: str = Field(min_length=64, max_length=64)
    rationale: str = Field(min_length=3, max_length=2000)


class ApprovalReportEvidenceRead(ApiModel):
    id: UUID
    modality: str
    start_ms: int | None
    end_ms: int | None
    precision: str
    description: str
    captured_at: AwareDatetime


class ApprovalReportFindingRead(ApiModel):
    id: UUID
    rule_id: str
    rule_version: str
    severity: str
    evidence_ids: list[UUID]
    start_ms: int | None
    end_ms: int | None
    evidence_text: str
    uncertainty: str
    suggested_action: str
    decision: Literal["dismissed", "incorrect"]
    decision_rationale: str
    decision_actor_user_id: UUID
    decided_at: AwareDatetime


class ApprovalReportRead(ApiModel):
    report_version: Literal["approval-report.v1"]
    exported_at: AwareDatetime
    current_status: Literal["approved"]
    approval_id: UUID
    analysis_id: UUID
    campaign_id: UUID
    campaign_name: str
    submission_version_id: UUID
    submission_version_no: int = Field(ge=1)
    rule_pack_version_id: UUID
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    caption_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer_user_id: UUID
    reviewer_display_name: str
    approved_at: AwareDatetime
    approval_rationale: str
    invocation_mode: Literal["fixture", "recorded", "live"]
    analysis_status: Literal["completed"]
    schema_version: str
    prompt_version: str
    model_versions: dict[str, str]
    required_coverage: list[str]
    observed_coverage: list[str]
    evidence: list[ApprovalReportEvidenceRead]
    findings: list[ApprovalReportFindingRead]
    limitations: list[str]


class FixRequestCreate(ApiModel):
    finding_ids: list[UUID] = Field(default_factory=list, max_length=100)


class CreatorFeedbackCreate(ApiModel):
    fix_request_draft_id: UUID
    message: str = Field(min_length=1, max_length=2000)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)

    @field_validator("message")
    @classmethod
    def message_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("feedback message must not be blank")
        return stripped

    @model_validator(mode="after")
    def time_range_is_complete_and_ordered(self) -> CreatorFeedbackCreate:
        if (self.start_ms is None) != (self.end_ms is None):
            raise ValueError("feedback timestamps must be supplied together")
        if self.start_ms is not None and self.end_ms is not None and self.end_ms <= self.start_ms:
            raise ValueError("feedback end_ms must be greater than start_ms")
        return self


class CreatorFeedbackRead(ApiModel):
    id: UUID
    submission_id: UUID
    submission_version_id: UUID
    analysis_id: UUID
    fix_request_draft_id: UUID
    version_no: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=2000)
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, ge=0)
    invocation_mode: Literal["fixture", "recorded", "live"]
    analysis_status: Literal["queued", "running", "completed", "partial", "failed", "cancelled"]
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    published_at: AwareDatetime
    historical: bool


class DeletionRequestCreate(ApiModel):
    resource_type: Literal["submission", "media_asset"]
    resource_id: UUID
