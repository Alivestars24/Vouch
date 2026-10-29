from __future__ import annotations

import hashlib
import hmac
import ipaddress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .auth import get_session
from .db import set_database_scope
from .errors import ApiError, forbidden
from .models import (
    CampaignCreator,
    GuestGrant,
    GuestSession,
    Membership,
    MembershipRole,
    Submission,
    Tombstone,
)

GUEST_COOKIE_NAME = "vouch_guest_session"
GUEST_COOKIE_PATH = "/api/v1/guest"
GUEST_ACCESS_ENDED_MESSAGE = (
    "This creator link is no longer available. Ask the sender for a new invitation."
)


@dataclass(frozen=True, slots=True)
class GuestPrincipal:
    organization_id: UUID
    grant_id: UUID
    session_id: UUID
    campaign_id: UUID
    creator_id: UUID
    submission_id: UUID
    allowed_actions: frozenset[str]
    session_expires_at: datetime
    database_function_backed: bool = False


def guest_access_ended() -> ApiError:
    return ApiError(401, "GUEST_ACCESS_ENDED", GUEST_ACCESS_ENDED_MESSAGE)


def require_guest_origin(request: Request) -> None:
    origin = request.headers.get("Origin")
    expected = request.app.state.settings.guest_public_origin
    if origin is None or not hmac.compare_digest(origin, expected):
        raise forbidden(
            "GUEST_ORIGIN_REJECTED",
            "This creator request did not come from the configured portal.",
        )


def guest_cookie_secure(public_origin: str) -> bool:
    return urlsplit(public_origin).scheme == "https"


def guest_client_bucket(request: Request) -> str:
    address = request.client.host if request.client else "unknown"
    try:
        parsed = ipaddress.ip_address(address)
        if isinstance(parsed, ipaddress.IPv4Address):
            minimized = str(ipaddress.ip_network(f"{parsed}/24", strict=False).network_address)
        else:
            minimized = str(ipaddress.ip_network(f"{parsed}/64", strict=False).network_address)
    except ValueError:
        minimized = address[:128]
    return hmac.new(
        request.app.state.settings.guest_rate_limit_key.encode("utf-8"),
        minimized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def guest_grant_is_authorized(
    session: Session,
    grant: GuestGrant,
    now: datetime,
    *,
    require_consumed: bool,
) -> bool:
    if (
        grant.revoked_at is not None
        or as_utc(grant.expires_at) <= now
        or (require_consumed and grant.consumed_at is None)
        or (not require_consumed and grant.consumed_at is not None)
    ):
        return False
    membership = session.scalar(
        select(Membership).where(
            Membership.organization_id == grant.organization_id,
            Membership.user_id == grant.issued_by_user_id,
            Membership.active.is_(True),
        )
    )
    if membership is None:
        return False
    current_roles = frozenset(
        session.scalars(
            select(MembershipRole.role).where(
                MembershipRole.organization_id == grant.organization_id,
                MembershipRole.membership_id == membership.id,
            )
        ).all()
    )
    qualifying_roles = (
        {"admin", "marketer"}
        if grant.scope_kind == "created_submission"
        else {"admin", "marketer", "reviewer"}
    )
    if current_roles.isdisjoint(qualifying_roles):
        return False
    rostered = session.scalar(
        select(CampaignCreator.id).where(
            CampaignCreator.organization_id == grant.organization_id,
            CampaignCreator.campaign_id == grant.campaign_id,
            CampaignCreator.creator_id == grant.creator_id,
        )
    )
    submission = session.scalar(
        select(Submission.id).where(
            Submission.organization_id == grant.organization_id,
            Submission.id == grant.submission_id,
            Submission.campaign_id == grant.campaign_id,
            Submission.creator_id == grant.creator_id,
            Submission.deleted_at.is_(None),
        )
    )
    denied = session.scalar(
        select(Tombstone.id).where(
            Tombstone.organization_id == grant.organization_id,
            Tombstone.resource_type == "submission",
            Tombstone.resource_id == grant.submission_id,
        )
    )
    return rostered is not None and submission is not None and denied is None


def get_guest_principal(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
) -> GuestPrincipal:
    settings = request.app.state.settings
    if settings.auth_mode == "supabase" and settings.guest_database_url is None:
        raise ApiError(
            503,
            "GUEST_RUNTIME_UNAVAILABLE",
            "Creator access is not configured for this environment.",
            True,
        )
    secret = request.cookies.get(GUEST_COOKIE_NAME, "")
    if not 20 <= len(secret) <= 500:
        raise guest_access_ended()
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    if settings.auth_mode == "supabase":
        row = session.execute(
            text("select * from vouch_private.resolve_guest_session(:digest)"),
            {"digest": digest},
        ).mappings().one_or_none()
        if row is None:
            raise guest_access_ended()
        set_database_scope(
            session,
            organization_id=row["organization_id"],
            guest_grant_id=row["grant_id"],
            guest_session_id=row["session_id"],
        )
        return GuestPrincipal(
            organization_id=row["organization_id"],
            grant_id=row["grant_id"],
            session_id=row["session_id"],
            campaign_id=row["campaign_id"],
            creator_id=row["creator_id"],
            submission_id=row["submission_id"],
            allowed_actions=frozenset(row["allowed_actions"]),
            session_expires_at=as_utc(row["session_expires_at"]),
            database_function_backed=True,
        )
    now = datetime.now(UTC)
    guest_session = session.scalar(
        select(GuestSession).where(GuestSession.session_secret_hash == digest)
    )
    if (
        guest_session is None
        or guest_session.revoked_at is not None
        or as_utc(guest_session.expires_at) <= now
    ):
        raise guest_access_ended()
    grant = session.scalar(
        select(GuestGrant).where(
            GuestGrant.id == guest_session.grant_id,
            GuestGrant.organization_id == guest_session.organization_id,
        )
    )
    if grant is None or not guest_grant_is_authorized(
        session, grant, now, require_consumed=True
    ):
        raise guest_access_ended()
    set_database_scope(
        session,
        organization_id=grant.organization_id,
        guest_grant_id=grant.id,
        guest_session_id=guest_session.id,
    )
    return GuestPrincipal(
        organization_id=grant.organization_id,
        grant_id=grant.id,
        session_id=guest_session.id,
        campaign_id=grant.campaign_id,
        creator_id=grant.creator_id,
        submission_id=grant.submission_id,
        allowed_actions=frozenset(grant.allowed_actions),
        session_expires_at=as_utc(guest_session.expires_at),
    )
