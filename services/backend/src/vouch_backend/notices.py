"""Immutable, server-owned local processing notices; not legal review or subject consent."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .errors import ApiError, not_found

CURRENT_NOTICE_VERSION = "campaign-check-2026-10-23.v1"
GUEST_NOTICE_VERSION = "creator-campaign-check-2026-10-26.v1"
_BODY = (
    "You authorize Vouch to process this campaign upload for campaign Check review. "
    "Model providers currently produce deterministic fixture evidence, not observations of your "
    "upload or legally certified results. Optional decoded media mode validates the actual file "
    "and temporarily normalizes it in an isolated local container; "
    "provider evidence stays fixture. "
    "Source access expires 30 days after the upload intent, without extending that original "
    "deadline on retry. Deletion or withdrawal blocks access, cancels pending work and scrubs "
    "application source content and derivatives; private Storage cleanup may remain pending or "
    "fail and is reported separately. Minimal authorization, provenance and audit records may "
    "remain. Backups and unverified provider copies are not covered by a completed application "
    "cleanup receipt. Standard processing does not promise zero retention, no training, a lawful "
    "basis or universal erasure. An authorized workspace admin or marketer may withdraw this "
    "authorization and request deletion. This acknowledgment is yours as a workspace member, "
    "not proof that every depicted person consented. "
    "This notice is a local draft, not legal review."
)

_GUEST_BODY = (
    "By continuing through this private creator link, you attest that you have the rights "
    "needed to provide this campaign source and authorize Vouch to process it for campaign "
    "Check review. Possession of the link identifies this portal session; it does not prove "
    "your legal identity or consent from every depicted person. Model providers currently "
    "produce deterministic fixture evidence, not observations of your upload or legally "
    "certified results. Optional decoded media mode validates the actual file and temporarily "
    "normalizes it in an isolated local container; provider evidence stays fixture. Source "
    "access expires 30 days after the upload intent without extending that original deadline "
    "on retry. Deletion may block access while private Storage or derivative cleanup remains "
    "pending or fails; minimal authorization, provenance, and audit records may remain. "
    "Backups and unverified provider copies are not covered by a completed application cleanup "
    "receipt. Standard processing does not promise zero retention, no training, a lawful basis, "
    "or universal erasure. Contact the brand representative who sent this link for withdrawal, "
    "deletion, or access help. This notice is a local draft, not legal review."
)


class ProcessingNotice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str
    purpose: Literal["campaign_check"]
    notice_hash: str
    title: str
    body: str
    published_at: datetime
    status: Literal["draft_local_only"]


CURRENT_NOTICE = ProcessingNotice(
    version=CURRENT_NOTICE_VERSION,
    purpose="campaign_check",
    notice_hash=hashlib.sha256(_BODY.encode("utf-8")).hexdigest(),
    title="Campaign Check processing authorization",
    body=_BODY,
    published_at=datetime(2026, 10, 23, tzinfo=UTC),
    status="draft_local_only",
)
GUEST_NOTICE = ProcessingNotice(
    version=GUEST_NOTICE_VERSION,
    purpose="campaign_check",
    notice_hash=hashlib.sha256(_GUEST_BODY.encode("utf-8")).hexdigest(),
    title="Creator campaign Check processing authorization",
    body=_GUEST_BODY,
    published_at=datetime(2026, 10, 26, tzinfo=UTC),
    status="draft_local_only",
)
NOTICE_REGISTRY = MappingProxyType(
    {
        CURRENT_NOTICE.version: CURRENT_NOTICE,
        GUEST_NOTICE.version: GUEST_NOTICE,
    }
)


def get_notice(version: str | None = None) -> ProcessingNotice:
    notice = NOTICE_REGISTRY.get(version or CURRENT_NOTICE_VERSION)
    if notice is None:
        raise not_found()
    return notice


def require_current_notice(version: str) -> ProcessingNotice:
    if version != CURRENT_NOTICE_VERSION:
        raise ApiError(
            409, "NOTICE_VERSION_STALE",
            "Reload the current processing notice and acknowledge it before uploading.",
        )
    return CURRENT_NOTICE


def get_guest_notice(version: str | None = None) -> ProcessingNotice:
    notice = NOTICE_REGISTRY.get(version or GUEST_NOTICE_VERSION)
    if notice is None or notice.version != GUEST_NOTICE_VERSION:
        raise not_found()
    return notice


def require_current_guest_notice(version: str) -> ProcessingNotice:
    if version != GUEST_NOTICE_VERSION:
        raise ApiError(
            409,
            "NOTICE_VERSION_STALE",
            "Reload the current creator processing notice and acknowledge it before uploading.",
        )
    return GUEST_NOTICE
